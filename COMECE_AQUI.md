# Começar a usar

Guia curto para quem vai rodar o projeto pela primeira vez. Não é preciso saber Python.

## 1. Instale o Python

Se o computador ainda não tem, baixe em <https://www.python.org/downloads/>.

No Windows, durante a instalação, marque a caixa **"Add Python to PATH"**. É a única escolha que costuma dar problema se passar batido.

No Linux (Ubuntu ou Debian):

```bash
sudo apt install python3 python3-venv
```

## 2. Baixe o projeto

```bash
git clone https://github.com/P3dr022/Radar_permanecia_Proj-IA.git
cd Radar_permanecia_Proj-IA
```

Quem preferir pode usar o botão **Code → Download ZIP** no GitHub e descompactar.

## 3. Rode

**Windows:** dois cliques em `executar.bat`.

**Linux ou macOS:**

```bash
./executar.sh
```

**Qualquer sistema, pelo terminal:**

```bash
python executar.py
```

Na primeira vez o programa monta sozinho o ambiente e instala as bibliotecas, o que leva um ou dois minutos. Depois aparece um menu:

```
  O que você quer fazer?

    1  Rodar tudo
    2  Calcular a evasão e validar
    3  Treinar os modelos
    4  Gerar o relatório HTML
    5  Montar a base nacional (~3 min)
    6  Só conferir o ambiente
    0  Sair
```

Digite o número e pressione Enter. Para quem já sabe o que quer, dá para pular o menu:

```bash
python executar.py tudo        # pipeline inteiro
python executar.py evasao      # calcula a evasão e roda os testes
python executar.py relatorio   # gera o relatório HTML
python executar.py checar      # só mostra o diagnóstico do ambiente
```

## 4. Veja o resultado

A opção 4 grava `resultados/relatorio.html`. Abra o arquivo com dois cliques: ele tem os números, as tabelas e os gráficos, e funciona em qualquer navegador, sem internet.

## Perguntas frequentes

**Preciso baixar os arquivos do INEP?** Não. Os dados já processados vêm no repositório e todas as análises rodam sem eles. Os ZIPs originais, que somam cerca de 570 MB, só são necessários para refazer a extração do zero; o endereço de cada um está no README.

**Apareceu "Python não foi encontrado".** O Python não está instalado ou não foi adicionado ao PATH. No Windows, reinstale marcando "Add Python to PATH".

**Apareceu erro ao criar o ambiente virtual no Linux.** Falta o pacote de ambientes virtuais: `sudo apt install python3-venv`.

**Posso rodar de novo sem problema?** Pode. Os scripts recalculam tudo a partir dos dados e sobrescrevem os resultados. O ambiente só é montado na primeira vez.

**Quanto tempo leva?** Os cálculos e modelos levam segundos. Montar a base nacional leva cerca de três minutos e precisa dos ZIPs do INEP.

## O que dizem os números

Antes de apresentar qualquer resultado, vale ler a seção **Limitações** do `README.md`. Os modelos deste projeto **não superam o chute trivial**, e esse é o principal achado: os indicadores públicos disponíveis não bastam para prever, escola a escola, quem vai perder alunos. O relatório mostra cada métrica ao lado da referência que ela precisaria superar, justamente para que isso não se perca.
