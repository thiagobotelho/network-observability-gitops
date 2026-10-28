# Fluxos e políticas


sampling=100 coleta uma amostra de aproximadamente um a cada cem pacotes segundo o agente e sua configuração; não é registro completo de tráfego. O eBPF observa a rede e requer privilégios específicos. Compare fluxos de uma conexão permitida e bloqueada, sem inferir ausência de tráfego a partir de uma amostra ausente.

## Relacionar camadas

NetworkPolicy é aplicada na rede; AuthorizationPolicy é aplicada pelo Envoy. Um HTTP 403 pode trafegar normalmente e não aparecer como drop no Network Traffic. Correlacione IP/porta e horário com auditoria OVN; para autorização HTTP, consulte response_code_details no log do proxy. NetworkEvents e auditoria OVN são fontes distintas.
