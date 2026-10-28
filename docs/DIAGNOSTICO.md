# Diagnóstico de rede no CRC

## Perfil

O overlay `overlays/desenvolvimento` ativa:

| Recurso | Uso |
|---|---|
| PacketDrop | Quantidade e motivo de descartes no host/OVS |
| DNSTracking | Respostas e latência DNS |
| FlowRTT | Latência TCP; não mede tempo de resposta HTTP |
| sampling 1 | Evita redução por amostragem durante os exercícios |

PacketDrop exige agente eBPF privilegiado. O Operator gerencia essa permissão;
não conceda SCC privilegiada aos clientes dos exercícios. O perfil mantém
Direct, Loki dedicado e métricas agregadas por namespace.

Aceite e produção herdam a base com sampling 100 e sem essas funcionalidades.
Esses overlays exigem dimensionamento e revisão de segurança antes do uso.
No perfil padrão NetworkEvents não está habilitado: a correlação com políticas depende de
OVNObservability, recurso Technology Preview. Não altere FeatureGate para
obter apenas a visualização de drops.

## Conferir implantação

Sincronize a Application `network-observability` após revisar o diff:

```bash
oc -n openshift-gitops get application network-observability
oc get flowcollector cluster -o jsonpath='{.spec.agent.ebpf}{"\n"}'
oc -n netobserv-privileged rollout status daemonset/netobserv-ebpf-agent --timeout=180s
oc -n netobserv rollout status daemonset/flowlogs-pipeline --timeout=180s
oc -n netobserv get pods
oc -n netobserv-privileged get pods
```

Confira `Ready=True` nas condições do FlowCollector. Um Loki com somente um
ingester pode apresentar aviso de disponibilidade; ele não comprova falha de
coleta. A confirmação funcional exige fluxos recentes.

## Console

1. Abra Observe → Network Traffic e atualize a página.
2. Selecione uma janela iniciada após a sincronização.
3. Filtre namespace, origem e destino do exercício.
4. Selecione a visão Packet Drops; use Manage columns para exibir descartes.
5. Expanda um fluxo e confira o motivo: prefixos SKB_DROP e OVS_DROP.
6. Use as visões DNS e RTT para investigar resolução e latência.

Fluxos antigos não recebem os novos campos retroativamente. A interface e os
rótulos das colunas dependem da versão do plugin.

## Exercício NetworkPolicy

No projeto mesh-apps-lab, aplique o cenário 02 e confirme:

- sleep → httpbin: HTTP 200.
- sleep-denied → httpbin: falha de transporte, sem resposta HTTP.
- DNS do cliente bloqueado continua funcional.

Correlacione horário, IPs atuais dos pods, porta de destino 8080 e sentido do
tráfego. O Service usa 8000 e encaminha ao pod em 8080.

Um drop pode ter várias causas; OVS_DROP_LAST_ACTION pode representar bloqueio
por política, mas não informa sozinho seu nome. Ausência de drop não prova
Allow. Um HTTP 403 do Envoy é rejeição L7 após a conexão chegar ao proxy.
Sampling 1 não garante ausência de perdas no pipeline; confira a saúde.

## Prometheus

Em Observe → Metrics, use:

```promql
sum(rate(netobserv_namespace_drop_packets_total[5m]))
```

```promql
sum(rate(netobserv_namespace_dns_flows_total[5m]))
```

```promql
histogram_quantile(0.95, sum by (le) (rate(netobserv_namespace_rtt_seconds_bucket[5m])))
```

```promql
histogram_quantile(0.95, sum by (le) (rate(netobserv_namespace_dns_latency_seconds_bucket[5m])))
```

Séries podem surgir somente após tráfego correspondente. O includeList usa
nomes sem o prefixo netobserv_; consultas PromQL usam o prefixo.
Confira também Observe → Alerting e o dashboard NetObserv/Health quando
disponível. Os alertas padrão dependem de funcionalidades e métricas habilitadas.

## Capacidade e reversão

```bash
oc adm top nodes
oc adm top pods -n netobserv
oc adm top pods -n netobserv-privileged
oc -n netobserv get pvc
oc -n netobserv get events --sort-by=.lastTimestamp
```

Sampling 1 aumenta volume de flows, armazenamento e carga. Monitore também
MinIO, Prometheus, reinícios e uso real dos volumes; PVC Bound não mede espaço
livre. Para uso contínuo de maior volume, dimensione coleta, retenção e S3.

Para voltar ao perfil leve, remova a referência `diagnostico.yaml` de
`overlays/desenvolvimento/kustomization.yaml`, revise o render e publique pelo
GitOps. O estado desejado volta a sampling 100, sem features e sem modo
privilegiado explícito. Aguarde o rollout e confira as permissões do novo pod.
Não apague Loki, PVCs ou a Application para reverter o perfil.

## Referências

- [Red Hat: packet drops, DNS e RTT](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/network_observability/nw-observe-network-traffic)
- [Red Hat: NetworkEvents e requisitos OVN](https://developers.redhat.com/articles/2024/11/19/monitor-ovn-networking-events-using-network-observability)
- [API FlowCollector](https://github.com/netobserv/network-observability-operator/blob/main/docs/FlowCollector.md)

Valide os campos contra a CRD instalada, além da documentação da versão.

Para o experimento separado, consulte [NETWORK-EVENTS.md](NETWORK-EVENTS.md).
