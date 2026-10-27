# Operação do armazenamento de fluxos

Prepare o armazenamento S3 e a configuração do Loki dedicado antes de sincronizar o FlowCollector:

```bash
scripts/bootstrap-netobserv-loki.sh
oc get flowcollector cluster
oc -n netobserv get lokistack,pods
```

Confira as proteções de contexto e os parâmetros do script. Credenciais devem permanecer em Secrets; não copie valores para o Git. Use RBAC restrito ao namespace dos Secrets, preserve PVCs e valide ingestão antes de depender dos fluxos no Console.

Para os procedimentos completos, consulte [COMO-USAR.md](COMO-USAR.md) e [POLITICAS.md](POLITICAS.md).
