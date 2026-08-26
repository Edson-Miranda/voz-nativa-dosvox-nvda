# Voz nativa do DOSVOX para NVDA

Sintetizador em português para o NVDA baseado na voz nativa do sistema DOSVOX,
desenvolvido na UFRJ a partir de 1993.

Este é um projeto independente de adaptação para o NVDA. Ele não é um produto
oficial do Projeto DOSVOX nem da NV Access.

## Recursos

- bancos Difones, Difones 2, Difones 3 e Difones 5;
- reprodução das gravações originais para letras, números e símbolos;
- conjunto alternativo de letras rápidas;
- opções Cortafala, Rapidinho e redução de volume;
- pausas e parâmetros de difones configuráveis em `dosvox.ini`;
- interrupção responsiva e síntese em fluxo para textos longos;
- tratamento de números, horários, valores em reais, pontuação e símbolos;
- integração com soletração e Ajuda de Entrada do NVDA.

## Estrutura

- `manifest.ini`: identificação e compatibilidade do complemento;
- `synthDrivers/vozNativaDoDosvox.py`: integração com o NVDA;
- `synthDrivers/dosvox_data/dosvox_native_core.py`: núcleo da síntese;
- `synthDrivers/dosvox_data/`: bancos, regras, configuração e gravações;
- `doc/pt_BR/readme.html`: ajuda exibida pelo NVDA;
- `tests/`: verificações automáticas;
- `build_nvda_addon.py`: geração do pacote instalável.

## Testar e gerar o pacote

Requer Python 3.

```powershell
python .\tests\run_tests.py
python .\build_nvda_addon.py
```

O pacote é criado em `dist/`. A pasta é ignorada pelo Git; arquivos publicados
devem ser anexados a uma versão do repositório.

## Instalação

Abra o arquivo `.nvda-addon` com o NVDA em execução, confirme a instalação e
reinicie o NVDA. Selecione depois “Voz nativa do DOSVOX” em Preferências,
Configurações, Fala, Sintetizador.

## Autoria e origem

- adaptação para o NVDA: Edson Miranda
  (`edson.demiranda.melo@gmail.com`);
- sistema e voz de origem: Projeto DOSVOX, desenvolvido no NCE/UFRJ a partir
  de 1993.

Consulte [NOTICE.md](NOTICE.md) e [LICENSE.md](LICENSE.md). A utilização e
redistribuição dos áudios e dados do DOSVOX neste complemento foram autorizadas
por Antônio Borges, conforme permissão confirmada pelo mantenedor Edson Miranda.