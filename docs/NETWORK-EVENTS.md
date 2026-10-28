# Network Events opcional no CRC

## Separação de responsabilidades

- argocd-gitops/bootstrap/ovn-observability: FeatureGate manual do cluster.
- argocd-gitops/optional/network-events: seleciona o perfil na mesma Application.
- overlays/desenvolvimento-network-events: coleta e métricas de NetworkEvents.

O padrão desenvolvimento continua com PacketDrop, DNS e RTT, sem NetworkEvents.
Aceite e produção não recebem recursos experimentais.

## Pré-requisito

Habilite OVNObservability pelo conjunto TechPreviewNoUpgrade e aguarde a
reconciliação conforme o [bootstrap](https://github.com/thiagobotelho/argocd-gitops/blob/main/bootstrap/ovn-observability/README.md).
Esse conjunto é irreversível e impede atualizações menores; não o habilite em
produção. O overlay de coleta não altera a FeatureGate.

## Coleta

O perfil adiciona NetworkEvents à lista existente e mantém sampling 1 e
agente privilegiado. Acrescenta namespace_network_policy_events_total ao
includeList. A permissão elevada é do agente; clientes do laboratório
continuam sem SCC privilegiada.

Via Argo, aplique optional/network-events no argocd-gitops. Se não houver
gerenciamento GitOps, aplique diretamente:

```bash
oc apply -k overlays/desenvolvimento-network-events
```

Não misture aplicação direta com a Application gerenciando outro perfil.

## Validar

```bash
oc get flowcollector cluster -o jsonpath='{.spec.agent.ebpf.features}{"\n"}{.status.conditions}{"\n"}'
oc -n netobserv-privileged rollout status daemonset/netobserv-ebpf-agent --timeout=180s
oc -n netobserv rollout status daemonset/flowlogs-pipeline --timeout=180s
oc adm top pods -n netobserv
oc adm top pods -n netobserv-privileged
```

No Console:

1. Atualize Observe → Network Traffic.
2. Selecione Network Events no seletor de visão.
3. Use janela recente e gere novas chamadas permitidas/bloqueadas.
4. Exiba Network Events em Manage columns e expanda os registros.
5. Confira ação, direção, namespace e nome da regra, quando informado.

Evite exigir destino Pod nos filtros: tentativas podem ser registradas como
Service antes do DNAT. Compare IPs/portas atuais e horário do curl. Eventos
antigos não são enriquecidos retroativamente e sampling 1 não garante entrega
sem perdas no pipeline.

Para monitorar a métrica:

```promql
sum(rate(netobserv_namespace_network_policy_events_total[5m]))
```

Um drop implícito pode identificar somente namespace/direção. NetworkPolicy
isola o destino e permite por regras aditivas; não invente uma regra deny.
HTTP 403 do Envoy continua sendo decisão L7, distinta da decisão OVN.
A auditoria em Observe → Logs permanece uma evidência complementar.

## Desativar coleta

No argocd-gitops, reaplique optional para voltar ao perfil desenvolvimento.
Isso remove NetworkEvents do FlowCollector, mas não desfaz TechPreviewNoUpgrade.
Não apague dados do Loki nem o namespace para trocar de perfil.

## Referências

- [Red Hat: OVNObservability e OVS sampling](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/pdf/ovn-kubernetes_network_plugin/index)
- [Red Hat: visualização de Network Events](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/network_observability/nw-observe-network-traffic)
