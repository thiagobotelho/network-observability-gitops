# network-observability-gitops

Network Observability Operator para OpenShift Local. O perfil CRC usa o
modelo `Direct`, indicado para clusters pequenos, amostragem conservadora e
métricas no Prometheus do OpenShift. Loki não é obrigatório.

```bash
oc apply -k overlays/desenvolvimento
```

Habilite somente após a stack principal estabilizar: o agente eBPF e o
processor consomem recursos adicionais e exigem `cluster-admin`.

Referência: documentação Network Observability do OpenShift 4.20.

## Ambientes e validação

```bash
oc kustomize overlays/desenvolvimento >/tmp/netobserv-dev.yaml
oc kustomize overlays/aceite >/tmp/netobserv-aceite.yaml
oc kustomize overlays/producao >/tmp/netobserv-prod.yaml
```

`oc apply --dry-run=client -k ...` requer o CRD `FlowCollector` instalado; se o
Operator ainda não estiver no cluster, valide com `oc kustomize`. Veja
`docs/AMBIENTES.md`.

## Automatizações preservadas e ajustadas

- `.github/workflows/validate.yml` foi preservado e ajustado para renderizar
  todos os Kustomizations, não apenas `overlays/crc`.
- Adicionados overlays padronizados `desenvolvimento`, `aceite` e `producao`.
