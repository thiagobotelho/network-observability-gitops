# Como usar o Network Observability

Este repositório instala o Network Observability Operator e um `FlowCollector`
para observar fluxos de rede do cluster OpenShift. Ele é opcional porque usa
eBPF, opera em nível de cluster e consome recursos extras.

## 1. O que ele entrega

- Operator Network Observability via OLM.
- `FlowCollector` único chamado `cluster`.
- Modelo `Direct`, mais simples para CRC/single-node.
- LokiStack dedicado em `netobserv` com tenant `openshift-network`.
- Sampling conservador para reduzir carga.
- Métricas de fluxo no Prometheus/OpenShift Monitoring.
- Plugin gráfico no Console do OpenShift, acessado em `Observe > Network Traffic`.
- `spec.networkPolicy.enable: true`, para o Operator gerenciar políticas de
  rede compatíveis com o pipeline.

## 2. Quando habilitar

Habilite depois que a stack principal estiver estável:

- OpenShift GitOps saudável;
- Prometheus/OpenShift Monitoring saudável;
- Grafana saudável;
- Loki do `loki-gitops` saudável, pois o bootstrap local reaproveita o MinIO;
- CRC com CPU/memória sobrando.

Use para responder perguntas como:

- quais namespaces estão conversando entre si;
- quais workloads geram mais tráfego;
- qual nó recebe mais ingress/egress;
- se uma NetworkPolicy está bloqueando tráfego esperado;
- se há tráfego inesperado entre aplicações.

## 3. Interface gráfica

Sim, existe interface gráfica. O Network Observability não expõe uma `Route`
própria para o usuário final; ele registra um `ConsolePlugin` e aparece dentro
do Console do OpenShift.

Obtenha a URL do Console:

```bash
oc get route console -n openshift-console \
  -o jsonpath='https://{.spec.host}{"\n"}'
```

Valide se o plugin foi registrado:

```bash
oc get consoleplugins | grep -E 'netobserv|NAME'
```

Valide os serviços internos do plugin:

```bash
oc -n netobserv get svc netobserv-plugin netobserv-plugin-metrics
oc -n openshift-netobserv-operator get svc netobserv-plugin-static
```

No Console:

1. Acesse a rota do Console do OpenShift.
2. Entre com um usuário administrador.
3. Vá em `Observe > Network Traffic`.
4. Use as abas:
   - `Overview`: visão agregada por namespace, workload, nó, pod ou serviço;
   - `Traffic flows`: tabela detalhada dos fluxos, com filtros, colunas e
     exportação;
   - `Topology`: grafo visual das comunicações entre recursos.

Também é possível encontrar visões filtradas a partir de páginas de recursos
como namespaces, workloads, nodes e services, quando o plugin está carregado no
Console.

Se o menu não aparecer:

```bash
oc get consoleplugins
oc get flowcollector cluster
oc -n openshift-console get pods
```

Depois faça logout/login ou recarregue o Console. Plugins dinâmicos podem exigir
alguns minutos até aparecerem na sessão do navegador.

## 4. Como investigar perguntas comuns

### Quais namespaces estão conversando entre si?

Na UI:

1. `Observe > Network Traffic > Topology`.
2. Em `Show advanced options`, use `Scope = Namespace`.
3. Observe as arestas entre namespaces e o volume/rate nas conexões.

No Prometheus/Grafana:

```promql
sum by (SrcK8S_Namespace, DstK8S_Namespace) (
  rate(namespace_flows_total[5m])
)
```

### Quais workloads geram mais tráfego?

Na UI:

1. `Overview`.
2. Altere o escopo para workload/owner, quando disponível.
3. Ordene por bytes/rate.

No Prometheus/Grafana:

```promql
topk(10, sum by (SrcK8S_OwnerName) (
  rate(workload_egress_bytes_total[5m])
))
```

### Qual nó recebe mais ingress/egress?

Use `Overview` com escopo de node ou consulte:

```promql
topk(10, sum by (DstK8S_HostName) (
  rate(node_ingress_bytes_total[5m])
))

topk(10, sum by (SrcK8S_HostName) (
  rate(node_egress_bytes_total[5m])
))
```

### Uma NetworkPolicy está bloqueando tráfego esperado?

Use a aba `Traffic flows` e filtre origem/destino esperados. Se a versão/recurso
do Operator estiver com eventos de rede habilitados, a tabela pode mostrar
informações de allow/drop relacionadas a NetworkPolicy. No perfil CRC deste
repositório, mantemos o modo leve por padrão; habilitar eventos detalhados pode
aumentar consumo de CPU/memória.

### Há tráfego inesperado entre aplicações?

Use `Topology` com `Scope = Namespace` ou `Scope = Owner`, remova filtros rápidos
restritivos e procure arestas inesperadas. Depois clique no componente/aresta e
vá para `Traffic flows` para ver IP, porta, protocolo, origem e destino.

## 5. Preparar o Loki dedicado do NetObserv

O Network Observability precisa de um LokiStack dedicado para a experiência
completa do Console, principalmente a tabela `Traffic flows`. O LokiStack de
logging em `openshift-logging` não deve ser reutilizado para flows de rede.

No CRC, este repo reaproveita apenas o MinIO local do `loki-gitops`, mas cria
um bucket e Secret próprios para o NetObserv:

```bash
cd network-observability-gitops
cp .env.example .env
scripts/bootstrap-netobserv-loki.sh
```

O script:

1. valida login com `oc`;
2. garante o namespace `netobserv`;
3. lê `openshift-logging/minio-credentials`;
4. cria/atualiza o Secret `netobserv/netobserv-loki-s3`;
5. cria o bucket `netobserv` no MinIO local.

Secret esperado:

```text
Namespace: netobserv
Secret:    netobserv-loki-s3
Chaves:    access_key_id, access_key_secret, bucketnames, endpoint, region
```

Criação manual equivalente:

```bash
oc -n netobserv create secret generic netobserv-loki-s3 \
  --from-literal=access_key_id='<minio-user>' \
  --from-literal=access_key_secret='<minio-password>' \
  --from-literal=bucketnames='netobserv' \
  --from-literal=endpoint='http://minio.openshift-logging.svc:9000' \
  --from-literal=region='us-east-1' \
  --dry-run=client -o yaml | oc apply -f -
```

Não versione esse Secret.

## 6. Habilitar via Argo CD opcional

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

## 7. Habilitar diretamente

Para aplicar sem Argo CD:

```bash
cd network-observability-gitops
oc apply -k overlays/desenvolvimento
```

Se a CRD `flowcollectors.flows.netobserv.io` ainda não existir, aguarde a
Subscription instalar o Operator e reaplique o overlay.

## 8. Políticas usadas neste perfil

O `FlowCollector` local usa:

```yaml
spec:
  namespace: netobserv
  deploymentModel: Direct
  loki:
    enable: true
    mode: LokiStack
    lokiStack:
      name: loki
      namespace: netobserv
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
- `loki.mode: LokiStack`: usa o LokiStack dedicado com tenant
  `openshift-network`.
- `sampling: 100`: coleta 1 em cada 100 fluxos, reduzindo overhead.
- `logTypes: Flows`: mantém o pipeline focado em fluxos de rede.
- `includeList`: reduz cardinalidade das métricas.
- `networkPolicy.enable: true`: permite que o Operator gere políticas para o
  namespace `netobserv`.

Detalhes da política local: [POLITICAS.md](POLITICAS.md).

## 9. Validar saúde

```bash
oc get flowcollector cluster -o yaml
oc get lokistack loki -n netobserv
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

## 10. Validar métricas no Prometheus/Grafana

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

## 11. NetworkPolicy e namespaces adicionais

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

## 12. Troubleshooting

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
- confirme que `oc get lokistack loki -n netobserv` está `Ready`;
- valide se as métricas existem no Prometheus;
- confirme se NetworkPolicy não bloqueia o caminho do pipeline.
- confirme que você está olhando uma janela de tempo recente na UI.
- recarregue o Console após instalar o plugin.

### Erro `lookup loki ... no such host`

Esse erro aparece quando o `FlowCollector` usa o default `Monolithic` e tenta
consultar `http://loki:3100`, mas não existe Service `loki` no namespace do
pipeline.

Correção aplicada neste repo:

```yaml
spec:
  loki:
    enable: true
    mode: LokiStack
    lokiStack:
      name: loki
      namespace: netobserv
```

Depois valide:

```bash
oc -n netobserv logs daemonset/flowlogs-pipeline --tail=80
oc -n netobserv logs deploy/netobserv-plugin --tail=80
```

### Log `Could not get max chunk age`

Quando o NetObserv usa `spec.loki.mode: LokiStack`, o `netobserv-plugin` pode
registrar a mensagem abaixo ao abrir algumas telas ou consultas:

```text
Could not get max chunk age: status URL endpoint is not available when using Loki operator
```

Esse log não é o mesmo problema do `lookup loki`. O caminho principal de
consulta continua sendo o gateway do LokiStack:

```text
https://loki-gateway-http.netobserv.svc.cluster.local.:8080/api/logs/v1/network/
```

Valide a saúde real olhando:

```bash
oc get lokistack loki -n netobserv
oc -n netobserv logs daemonset/flowlogs-pipeline --since=5m
oc get flowcollector cluster
```

No CRC, `LokiStack` com `size: 1x.demo` também pode reportar aviso de apenas um
ingester. Isso é aceitável para laboratório local, mas não é configuração de
alta disponibilidade.

## 13. Remover

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
- Observing network traffic: <https://docs.okd.io/latest/observability/network_observability/observing-network-traffic.html>
- NetworkPolicy no FlowCollector: <https://docs.redhat.com/en/documentation/openshift_container_platform/4.19/html/network_observability/network-observability-network-policy>
- Network Observability Operator upstream: <https://github.com/netobserv/network-observability-operator>
- FlowCollector API: <https://github.com/netobserv/network-observability-operator/blob/main/docs/FlowCollector.md>
