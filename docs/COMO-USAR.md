# Como usar o Network Observability

Este repositório instala o Network Observability Operator e um `FlowCollector`
para observar fluxos de rede do cluster OpenShift. Ele é opcional porque usa
eBPF, opera em nível de cluster e consome recursos extras.

## 1. O que ele entrega

- Operator Network Observability via OLM.
- `FlowCollector` único chamado `cluster`.
- Modelo `Direct`, mais simples para CRC/single-node.
- Sampling conservador para reduzir carga.
- Métricas de fluxo no Prometheus/OpenShift Monitoring.
- `spec.networkPolicy.enable: true`, para o Operator gerenciar políticas de
  rede compatíveis com o pipeline.

## 2. Quando habilitar

Habilite depois que a stack principal estiver estável:

- OpenShift GitOps saudável;
- Prometheus/OpenShift Monitoring saudável;
- Grafana saudável;
- Loki/Tempo opcionais conforme o tipo de investigação;
- CRC com CPU/memória sobrando.

Use para responder perguntas como:

- quais namespaces estão conversando entre si;
- quais workloads geram mais tráfego;
- qual nó recebe mais ingress/egress;
- se uma NetworkPolicy está bloqueando tráfego esperado;
- se há tráfego inesperado entre aplicações.

## 3. Habilitar via Argo CD opcional

No `argocd-gitops`, o Network Observability fica em `optional/` para não pesar
em instalações mínimas do CRC.

```bash
cd argocd-gitops
oc apply -k optional
```

Depois acompanhe:

```bash
oc -n openshift-gitops get application network-observability
oc -n netobserv get pods
oc get flowcollector cluster
```

## 4. Habilitar diretamente

Para aplicar sem Argo CD:

```bash
cd network-observability-gitops
oc apply -k overlays/desenvolvimento
```

Se a CRD `flowcollectors.flows.netobserv.io` ainda não existir, aguarde a
Subscription instalar o Operator e reaplique o overlay.

## 5. Políticas usadas neste perfil

O `FlowCollector` local usa:

```yaml
spec:
  namespace: netobserv
  deploymentModel: Direct
  networkPolicy:
    enable: true
  agent:
    ebpf:
      sampling: 100
  processor:
    logTypes: Flows
    metrics:
      includeList:
        - namespace_flows_total
        - node_ingress_bytes_total
        - node_egress_bytes_total
        - workload_ingress_bytes_total
        - workload_egress_bytes_total
```

Interpretação:

- `Direct`: evita componentes centrais extras no CRC.
- `sampling: 100`: coleta 1 em cada 100 fluxos, reduzindo overhead.
- `logTypes: Flows`: mantém o pipeline focado em fluxos de rede.
- `includeList`: reduz cardinalidade das métricas.
- `networkPolicy.enable: true`: permite que o Operator gere políticas para o
  namespace `netobserv`.

Detalhes da política local: [POLITICAS.md](POLITICAS.md).

## 6. Validar saúde

```bash
oc get flowcollector cluster -o yaml
oc -n netobserv get pods,svc
oc -n netobserv get events --sort-by=.lastTimestamp | tail -50
```

Se houver Metrics UI:

```bash
oc adm top pods -n netobserv
```

Em CRC, acompanhe CPU/memória após habilitar:

```bash
oc adm top pods -A | grep -E 'netobserv|openshift-monitoring'
```

## 7. Validar métricas no Prometheus/Grafana

Procure por métricas como:

```promql
namespace_flows_total
node_ingress_bytes_total
node_egress_bytes_total
workload_ingress_bytes_total
workload_egress_bytes_total
```

Exemplos:

```promql
sum by (SrcK8S_Namespace, DstK8S_Namespace) (rate(namespace_flows_total[5m]))
sum by (SrcK8S_OwnerName) (rate(workload_egress_bytes_total[5m]))
sum by (DstK8S_OwnerName) (rate(workload_ingress_bytes_total[5m]))
```

Os nomes de labels podem variar conforme versão do Operator. Valide no
Prometheus antes de fixar dashboards/alertas.

## 8. NetworkPolicy e namespaces adicionais

Quando Loki, Kafka ou exporters estiverem em namespaces com NetworkPolicy
restritiva, inclua os namespaces em `spec.networkPolicy.additionalNamespaces`.
No CRC atual, o perfil não envia flows para Loki/Kafka, então a configuração
permanece mínima.

Exemplo de evolução:

```yaml
spec:
  networkPolicy:
    enable: true
    additionalNamespaces:
      - openshift-console
      - openshift-monitoring
      - openshift-logging
      - grafana
```

Só adicione namespaces necessários. Mais permissões significam uma superfície
maior de comunicação.

## 9. Troubleshooting

### FlowCollector não existe

```bash
oc get crd flowcollectors.flows.netobserv.io
oc get subscription -A | grep -i observ
```

Aguarde o Operator instalar a CRD e reaplique.

### Pods do netobserv não sobem

```bash
oc -n netobserv get pods
oc -n netobserv describe pod <pod>
oc -n netobserv logs <pod>
```

Procure problemas de SCC, permissões, imagem ou recursos insuficientes.

### CRC ficou pesado

- aumente `agent.ebpf.sampling`;
- reduza `processor.metrics.includeList`;
- desabilite o app opcional quando não estiver investigando;
- avalie CPU/memória com `oc adm top`.

### Fluxos não aparecem

- gere tráfego entre workloads;
- confirme que os pods do `netobserv` estão prontos;
- valide se as métricas existem no Prometheus;
- confirme se NetworkPolicy não bloqueia o caminho do pipeline.

## 10. Remover

Se foi aplicado via Argo CD opcional:

```bash
oc -n openshift-gitops delete application network-observability
```

Se foi aplicado diretamente:

```bash
oc delete -k overlays/desenvolvimento
```

Depois confirme:

```bash
oc get flowcollector cluster
oc -n netobserv get pods
```

## Referências oficiais

- Red Hat/OpenShift Network Observability: <https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/network_observability/>
- NetworkPolicy no FlowCollector: <https://docs.redhat.com/en/documentation/openshift_container_platform/4.19/html/network_observability/network-observability-network-policy>
- Network Observability Operator upstream: <https://github.com/netobserv/network-observability-operator>
- FlowCollector API: <https://github.com/netobserv/network-observability-operator/blob/main/docs/FlowCollector.md>
