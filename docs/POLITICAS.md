# Políticas do Network Observability

O `network-observability-gitops` é opcional no app-of-apps porque coleta fluxos
em nível de cluster, usa eBPF e exige permissões administrativas. A política
base segue o perfil local/CRC e pode ser reforçada por ambiente.

## Políticas aplicadas

- `spec.networkPolicy.enable: true`: solicita que o Operator aplique as
  NetworkPolicies suportadas pelo FlowCollector.
- `spec.networkPolicy.additionalNamespaces` não é customizado no CRC; o
  Operator usa os padrões documentados para console e monitoring. Se Loki,
  Kafka ou exporters forem movidos para namespaces protegidos por NetworkPolicy,
  inclua explicitamente esses namespaces antes de habilitar o recurso.
- `spec.loki.mode: LokiStack`: usa um LokiStack dedicado no namespace
  `netobserv`, com tenant mode `openshift-network`.
- `deploymentModel: Direct`: reduz componentes centrais no CRC.
- `agent.ebpf.sampling: 100`: usa amostragem 1:100 de pacotes para diminuir carga em
  single-node.
- `processor.logTypes: Flows`: mantém foco nos fluxos de rede.
- `processor.metrics.includeList`: limita cardinalidade a métricas úteis para
  namespace, node e workload.

## Ambiente desenvolvimento

- Usar apenas após Loki de logging, MinIO, Prometheus e Grafana estarem
  saudáveis.
- Executar `scripts/bootstrap-netobserv-loki.sh` antes da primeira sincronização
  para criar o Secret S3 e bucket do LokiStack dedicado.
- Usar sampling 1 para diagnóstico, PacketDrop, DNSTracking e FlowRTT.
- O agente eBPF executa privilegiado; clientes das aplicações não recebem essa permissão.
- Incluir métricas agregadas de drops, DNS e RTT, sem séries por pod.
- Não habilitar NetworkEvents nem alterar FeatureGate do cluster.
- Acompanhar carga e armazenamento; para reduzir coleta, aumentar sampling no Git.
- Consultar [DIAGNOSTICO.md](DIAGNOSTICO.md) para filtros, consultas e reversão.
- Manter o componente como opt-in via `argocd-gitops/optional`, para não
  consumir recursos do CRC em instalações mínimas.
- Validar overhead com:

```bash
oc get flowcollector cluster
oc -n netobserv get pods
oc adm top pods -n netobserv
```

## Ambiente aceite

- Ajustar sampling conforme volume do cluster.
- Validar integração com console OpenShift e Grafana.
- Confirmar se flows devem ser enviados também ao Loki.

## Ambiente producao

- Revisar impacto de eBPF por nó.
- Definir política de retenção e acesso aos fluxos.
- Avaliar Kafka para alto volume.
- Definir alertas de saúde do Operator e do pipeline.
- Validar NetworkPolicies geradas antes de aplicar em clusters restritos.

Referência oficial: documentação Red Hat/OpenShift Network Observability,
especialmente configuração do `FlowCollector` e NetworkPolicy.
