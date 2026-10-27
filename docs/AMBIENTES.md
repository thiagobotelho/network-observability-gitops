# Ambientes

Este repositório usa `base/` e `overlays/{desenvolvimento,aceite,producao}`.

- `desenvolvimento`: `FlowCollector` em modo `Direct` com sampling conservador para CRC.
- `aceite`: ajuste sampling, Loki e recursos para homologação.
- `producao`: valide overhead eBPF, retenção, visibilidade no console e integrações com Loki/Grafana.

Validação:

```bash
oc kustomize overlays/desenvolvimento >/tmp/netobserv-dev.yaml
oc kustomize overlays/aceite >/tmp/netobserv-aceite.yaml
oc kustomize overlays/producao >/tmp/netobserv-prod.yaml
```

Observação: `oc apply --dry-run=client -k ...` exige que o CRD `FlowCollector`
já exista no cluster. Sem o Operator/CRD instalado, use `oc kustomize` como
validação declarativa.

## Classe de armazenamento

LokiStack exige storageClassName. O overlay desenvolvimento seleciona a classe do OpenShift Local crc-csi-hostpath-provisioner. Confira sua existência antes de aplicar; caso a distribuição use outro provisionador, altere o patch. Em aceite e produção, substitua classe-rwo-exemplo por uma StorageClass RWO existente, com capacidade e recuperação definidas. A classe de dados de ingesters/queriers não substitui o backend S3 dos blocos.
