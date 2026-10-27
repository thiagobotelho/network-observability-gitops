# Fluxos e políticas

## O que observar

sampling=100 coleta uma amostra de aproximadamente um a cada cem pacotes segundo o agente e sua configuração; não é registro completo de tráfego. O eBPF observa a rede e requer privilégios específicos. Compare fluxos de uma conexão permitida e bloqueada, sem inferir ausência de tráfego a partir de uma amostra ausente.

## Roteiro de leitura e validação

1. Leia o README e identifique o componente que recebe a configuração.
2. Confira namespaces, seletores, portas, identidades e dependências nos exemplos.
3. Ajuste apenas os campos necessários em um ambiente isolado; não use credenciais de produção.
4. Valide sintaxe e contratos locais antes de aplicar. Registre o resultado real separado deste guia.
5. Execute um caso permitido e um caso negado, conferindo a causa da resposta.
6. Defina reversão por recurso/arquivo e preserve dados persistentes antes de mudanças.

Os comentários dos manifests explicam escolhas; não comprovam disponibilidade do componente. Exemplos fora de entradas Kustomize não são implantados automaticamente.
