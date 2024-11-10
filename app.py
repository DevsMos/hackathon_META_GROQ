from flask import Flask, request, jsonify
import pandas as pd
from crewai import Task, Crew, Agent, Process
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os
import random
from groq import Groq
import json
from openai import OpenAI  # Para geração de imagens com DALL-E
import base64
import requests

print("hellow")

# Configurações das APIs
TWILIO_ACCOUNT_SID = "AC0a59f6fbbd9bf09609953b98d14c8b84"
TWILIO_AUTH_TOKEN = "2f178c9a1fe785b7d9c1b3472b69909a"
TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"

# Configuração do cliente Twilio
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Inicializar a aplicação Flask
app = Flask(__name__)

# Configuração da Groq API
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

# Adicionar nas configurações
OPENAI_API_KEY = "sua_chave_openai"  # Você precisará de uma chave da OpenAI
client_openai = OpenAI(api_key=OPENAI_API_KEY)

# Função para carregar dados do CSV
def carregar_dados(csv_path: str) -> pd.DataFrame:
    csv_path = os.path.join(os.getcwd(), 'lista.csv')
    print(f"Tentando carregar CSV de: {csv_path}")
    df = pd.read_csv(csv_path)
    print("CSV carregado com sucesso")
    
    # Padronizar nomes das colunas e valores
    df.columns = df.columns.str.lower()
    df['tipo'] = df['tipo'].str.lower()
    df['cpf'] = df['cpf'].astype(str).str.strip()  # Remove espaços e converte para string
    print("Colunas após normalização:", df.columns.tolist())
    return df

# Função Mock para validar débitos no Serasa
def validar_debitos_serasa(cpf: str):
    if cpf == "22054122807":
        return [
            {"tipo": "Conta de Luz", "valor": 200},
            {"tipo": "Financiamento Itaú", "valor": 900},
            {"tipo": "Bar do Tonico", "valor": 15000}
        ]
    return []

# Definir o agente de análise financeira com CrewAI
print("# Definir o agente de análise financeira com CrewAI")
finance_agent = Agent(
    role="Analista Financeiro e Educador",
    goal="Avaliar a situação financeira do usuário e fornecer recomendações educativas personalizadas",
    backstory=(
        "Você é um analista financeiro especializado em educação financeira, "
        "com vasta experiência em ajudar pessoas a melhorarem sua relação com dinheiro. "
        "Você analisa padres de gastos e sugere mudanças práticas e educativas."
    ),
    verbose=True
)

# Definir a tarefa para o agente com CrewAI
finance_task = Task(
    description=(
        "Analise os dados financeiros do usuário com CPF {cpf}. Compare as informações "
        "do CSV com as do Serasa e identifique qualquer discrepância que possa indicar fraude."
    ),
    expected_output="Relatório detalhado de débitos, créditos e possíveis fraudes.",
    agent=finance_agent
)

def gerar_dica_financeira(perfil_gastos):
    """Gera uma dica financeira personalizada e dinâmica usando Groq"""
    try:
        prompt = f"""
        Como consultor financeiro especializado, analise o perfil financeiro abaixo e gere 
        uma dica personalizada e específica para a situação do usuário:

        PERFIL FINANCEIRO:
        {json.dumps(perfil_gastos, indent=2)}
        
        Considere:
        1. A proporção entre débitos e créditos
        2. Os principais tipos de gastos
        3. Padrões de comportamento financeiro
        4. Categoria com maior gasto
        5. Se há gastos em lazer/entretenimento
        6. A situação geral (endividado ou equilibrado)

        A dica deve:
        1. Ser específica para os gastos mais problemáticos do usuário
        2. Incluir uma ação prática que pode ser implementada imediatamente
        3. Considerar o contexto completo das finanças
        4. Ser motivadora e educativa
        5. Incluir números ou percentuais quando relevante
        6. Usar emojis apropriados
        7. Ter no máximo 3 linhas
        8. Ser em português

        Exemplos de contextos:
        - Se gasta muito em bar/apostas: Foque em alternativas de lazer econômicas
        - Se tem muitas dívidas: Priorize a quitação das dívidas mais caras
        - Se está equilibrado: Sugira investimentos ou reserva de emergência
        """

        completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um consultor financeiro especializado em educação financeira que fornece dicas práticas, personalizadas e acionáveis."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.8,
            max_tokens=150,
        )

        dica = completion.choices[0].message.content.strip()
        
        # Garantir que a dica comece com emoji se não começar
        if not any(c in dica[:2] for c in ['💡', '💰', '📊', '🎯', '💪', '🚀']):
            dica = '💡 ' + dica

        return dica

    except Exception as e:
        print(f"Erro ao gerar dica com Groq: {str(e)}")
        return "💡 Mantenha um controle regular dos seus gastos e estabeleça metas financeiras claras."

# Atualizar a função analisar_perfil_financeiro para incluir mais informações
def analisar_perfil_financeiro(debitos, creditos):
    """Analisa o perfil financeiro e retorna recomendações educativas"""
    recomendacoes = []
    
    # Converter valores para float para garantir serialização JSON
    total_debitos = float(sum(d['valor'] for d in debitos))
    total_creditos = float(creditos)
    
    # Categorizar gastos
    categorias = {}
    for debito in debitos:
        valor = float(debito['valor'])  # Converter para float
        if 'bar' in debito['tipo'].lower() or 'apostas' in debito['tipo'].lower():
            categorias['lazer'] = float(categorias.get('lazer', 0) + valor)
        elif 'luz' in debito['tipo'].lower():
            categorias['essenciais'] = float(categorias.get('essenciais', 0) + valor)
        elif 'banco' in debito['tipo'].lower() or 'financiamento' in debito['tipo'].lower():
            categorias['financeiro'] = float(categorias.get('financeiro', 0) + valor)
    
    # Análise e recomendações
    if total_debitos > total_creditos:
        recomendacoes.append(
            "🚨 Alerta: Seus gastos estão maiores que sua renda. "
            "Recomendamos criar um orçamento mensal e seguir a regra 50-30-20:\n"
            "- 50% para necessidades básicas\n"
            "- 30% para gastos pessoais\n"
            "- 20% para investimentos e emergências"
        )
    
    if categorias.get('lazer', 0) > total_creditos * 0.3:
        recomendacoes.append(
            "📊 Seus gastos com lazer estão acima do recomendado. "
            "Considere estabelecer um limite mensal de 30% da sua renda para estas despesas."
        )
    
    if categorias.get('financeiro', 0) > total_creditos * 0.4:
        recomendacoes.append(
            "💰 Atenção aos compromissos financeiros:\n"
            "- Evite usar mais de 40% da renda com dívidas\n"
            "- Considere renegociar dívidas com juros altos\n"
            "- Pesquise sobre portabilidade de dívidas"
        )
    
    # Preparar perfil de gastos para JSON
    perfil_gastos = {
        "total_creditos": float(total_creditos),
        "total_debitos": float(total_debitos),
        "categorias": {k: float(v) for k, v in categorias.items()},
        "principais_gastos": [
            {"tipo": d["tipo"], "valor": float(d["valor"])} 
            for d in sorted(debitos, key=lambda x: x["valor"], reverse=True)[:3]
        ],
        "situacao": "endividado" if total_debitos > total_creditos else "equilibrado",
        "razao_divida_renda": float(total_debitos / total_creditos if total_creditos > 0 else 0),
        "percentual_lazer": float(categorias.get('lazer', 0) / total_creditos * 100 if total_creditos > 0 else 0)
    }
    
    return recomendacoes, perfil_gastos

def gerar_badge_ascii(perfil_gastos):
    """Gera uma badge em ASCII art dinâmica e personalizada usando Groq"""
    try:
        prompt = f"""
        Como um artista ASCII criativo, crie uma badge única e divertida baseada no seguinte 
        perfil financeiro:
        {json.dumps(perfil_gastos, indent=2)}

        REGRAS PARA CRIAÇÃO:
        1. Analise o perfil e escolha um tema baseado no comportamento financeiro dominante
        2. Crie uma arte ASCII que represente visualmente a situação
        3. Use caracteres ASCII para criar detalhes visuais interessantes
        4. Inclua elementos que representem dinheiro (₿, $, €, ¢)
        5. Mantenha o tamanho máximo de 10 linhas para a arte
        6. Adicione um título criativo com emojis relacionados
        7. Inclua uma frase motivacional ou bem-humorada

        EXEMPLOS DE TEMAS:
        - Para gastador em bares:
        🍺 REI DO HAPPY HOUR 🍺
        ╔═══════════════╗
        ║   [_____]     ║
        ║    |$$$|      ║
        ║  \\(°□°)/     ║
        ║   $═══$      ║
        ╚═══════════════╝
        "Transformando salário em histórias desde 2024!"

        - Para investidor equilibrado:
        💎 MESTRE DAS FINANÇAS 💎
        ╔════════════════╗
        ║    /█████\\     ║
        ║   [$] [$]      ║
        ║    \\___/       ║
        ║  《₿》《₿》    ║
        ╚════════════════╝
        "Equilibrando contas como um profissional!"

        - Para endividado em recuperação:
        🚀 RUMO AO AZUL 🚀
        ╔════════════════╗
        ║    ╭─────╮     ║
        ║    │ $ $ │     ║
        ║    ╰─────╯     ║
        ║  ↗️ 📈 ↗️      ║
        ╚════════════════╝
        "Saindo do vermelho com estilo!"

        Analise o perfil e crie uma badge TOTALMENTE NOVA e ÚNICA que reflita:
        1. O principal comportamento financeiro
        2. A proporção entre débitos e créditos
        3. O tipo de gastos mais significativo
        4. A situação atual (endividado/equilibrado)
        5. Uma mensagem motivacional personalizada

        A resposta deve seguir exatamente este formato:
        [TÍTULO COM EMOJIS]
        [ARTE ASCII]
        [FRASE MOTIVACIONAL]
        """

        completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um artista ASCII especializado em criar badges gamificadas e divertidas que representam perfis financeiros."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.9,
            max_tokens=400,
        )

        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao gerar badge: {str(e)}")
        return """
🎯 BADGE PADRÃO 🎯
╔══════════════╗
║    $___$     ║
║    |   |     ║
║    |₿₿₿|     ║
║    \\___/     ║
╚══════════════╝
"Continue sua jornada financeira!"
"""

def validar_autenticidade(dados_declarados, dados_serasa, perfil_gastos):
    """Gera uma análise de autenticidade usando Groq"""
    try:
        dados_processados = {
            "declarados": {
                "debitos": [
                    {"tipo": d["tipo"], "valor": float(d["valor"])} 
                    for d in dados_declarados["debitos"]
                ],
                "creditos": float(dados_declarados["creditos"])
            },
            "serasa": [
                {"tipo": d["tipo"], "valor": float(d["valor"])} 
                for d in dados_serasa
            ],
            "perfil": {
                k: (float(v) if isinstance(v, (int, float)) else v)
                for k, v in perfil_gastos.items()
                if k != "categorias"
            }
        }
        
        prompt = f"""
        Como especialista em análise de autenticidade financeira, avalie este caso de forma objetiva:

        DADOS DECLARADOS:
        {json.dumps(dados_processados["declarados"], indent=2)}

        SERASA:
        {json.dumps(dados_processados["serasa"], indent=2)}

        PERFIL:
        {json.dumps(dados_processados["perfil"], indent=2)}

        Regras de análise:
        1. Compare APENAS os valores que aparecem em ambas as fontes
        2. Pequenas diferenças (até 10%) são aceitáveis
        3. Foque nos débitos mais significativos
        4. Considere o contexto dos gastos
        5. Seja direto e objetivo

        Responda EXATAMENTE neste formato:

        [SELO]
        ✅ VERIFICADO (se mais de 80% dos valores batem)
        ⚠️ REQUER ATENÇÃO (se 50-80% dos valores batem)
        🚫 POSSÍVEL FRAUDE (se menos de 50% dos valores batem)

        [CONFIABILIDADE]
        Número de 0 a 100%

        [ANÁLISE]
        - Ponto 1 (máximo 2 linhas)
        - Ponto 2 (máximo 2 linhas)
        - Ponto 3 (máximo 2 linhas)

        [CONCLUSÃO]
        Uma linha direta: Ajudar ou não, e por quê.
        """

        completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um auditor financeiro experiente que faz análises diretas e objetivas."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.7,
            max_tokens=300,  # Reduzido para respostas mais concisas
        )

        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao gerar validação: {str(e)}")
        return "⚠️ Análise temporariamente indisponível"

def enviar_mensagem_whatsapp(telefone_remetente, mensagem):
    """Envia mensagem pelo WhatsApp dividindo em partes lógicas"""
    try:
        # Dividir a mensagem em seções lógicas
        partes = []
        
        if "📊 Análise financeira" in mensagem:
            # Dividir em seções principais
            secoes = {
                "RESUMO": mensagem.split("📝 Detalhamento")[0],
                "DÉBITOS": "📝 Detalhamento" + mensagem.split("📝 Detalhamento")[1].split("🔍 Débitos")[0],
                "SERASA": "🔍 Débitos" + mensagem.split("🔍 Débitos")[1].split("🤖 VALIDAÇÃO")[0],
                "VALIDAÇÃO": "🤖 VALIDAÇÃO" + mensagem.split("🤖 VALIDAÇÃO")[1].split("🏆 SUA BADGE")[0],
                "BADGE": "🏆 SUA BADGE" + mensagem.split("🏆 SUA BADGE")[1]
            }
            
            # Adicionar cada seção como uma parte
            for titulo, conteudo in secoes.items():
                if conteudo.strip():
                    # Dividir conteúdo grande em partes menores
                    if len(conteudo) > 1500:
                        chunks = [conteudo[i:i+1500] for i in range(0, len(conteudo), 1500)]
                        for chunk in chunks:
                            partes.append(chunk.strip())
                    else:
                        partes.append(conteudo.strip())
        else:
            # Se for uma mensagem simples, enviar diretamente
            partes.append(mensagem)
        
        # Enviar cada parte
        for i, parte in enumerate(partes):
            if parte.strip():  # Enviar apenas se houver conteúdo
                twilio_client.messages.create(
                    from_=TWILIO_PHONE_NUMBER,
                    to=telefone_remetente,
                    body=parte.strip()
                )
                print(f"Parte {i+1}/{len(partes)} enviada: {len(parte)} caracteres")
        
        return True
    except Exception as e:
        print(f"Erro ao enviar mensagem: {str(e)}")
        return False

def gerar_dicas_educacionais(perfil_gastos, validacao):
    """Gera dicas educacionais personalizadas usando Groq"""
    try:
        prompt = f"""
        Como educador financeiro, analise o perfil e a validação abaixo para gerar 
        dicas educacionais personalizadas:

        PERFIL FINANCEIRO:
        {json.dumps(perfil_gastos, indent=2)}

        VALIDAÇÃO:
        {validacao}

        Gere 3 dicas educacionais que:
        1. Sejam específicas para o perfil do usuário
        2. Foquem em educação financeira
        3. Incluam exemplos práticos
        4. Usem linguagem acessível
        5. Motivem mudanças positivas

        Para cada dica, considere:
        - Comportamentos problemáticos identificados
        - Alternativas mais saudáveis
        - Impacto a longo prazo
        - Benefícios da mudança
        - Próximos passos práticos

        Formato da resposta:
        💡 DICAS EDUCACIONAIS:

        1. [Primeira dica com emoji] (foco no problema mais urgente)
        2. [Segunda dica com emoji] (foco em mudança de comportamento)
        3. [Terceira dica com emoji] (foco em planejamento futuro)

        [DESAFIO SEMANAL]
        Uma meta específica e alcançável para a próxima semana
        """

        completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um educador financeiro especializado em transformar vidas através da educação financeira."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.8,
            max_tokens=400,
        )

        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao gerar dicas educacionais: {str(e)}")
        return "💡 Mantenha um registro diário de seus gastos e estabeleça metas realistas."

# Webhook do Twilio para receber mensagens do WhatsApp e responder com a análise financeira
@app.route('/webhook', methods=['POST'])
def webhook_twilio():
    try:
        # Captura o corpo da mensagem recebida
        message_body = request.form.get('Body', '')
        telefone_remetente = request.form.get('From', '')
        
        print(f"Mensagem recebida: '{message_body}' de {telefone_remetente}")
        
        # Extrair o CPF da mensagem e limpar
        cpf = str(message_body).strip()
        print(f"CPF após limpeza: '{cpf}'")
        
        # Carregar dados e verificar o CPF
        dados = carregar_dados('lista.csv')
        
        # Debug dos dados
        print("\nDados únicos de CPF no CSV:", dados['cpf'].unique())
        print(f"Procurando CPF: '{cpf}'")
        
        # Comparação mais robusta
        user_data = dados[dados['cpf'].str.strip() == cpf.strip()]
        
        print(f"Registros encontrados: {len(user_data)}")
        print("Dados encontrados:")
        print(user_data)
        
        if user_data.empty:
            resposta = f"CPF {cpf} não encontrado na nossa base de dados."
        else:
            # Preparar dados declarados e débitos encontrados
            debitos_encontrados = [
                {
                    'tipo': row['nome instituição'],
                    'valor': row['valor']
                }
                for _, row in user_data[user_data['tipo'].str.lower() == 'débito'].iterrows()
            ]
            
            total_credit = user_data[user_data['tipo'].str.lower() == 'crédito']['valor'].sum()
            
            dados_declarados = {
                'debitos': debitos_encontrados,
                'creditos': total_credit
            }
            
            # Obter dados do Serasa
            dados_serasa = validar_debitos_serasa(cpf)
            
            # Análise financeira e recomendações
            recomendacoes, perfil_gastos = analisar_perfil_financeiro(debitos_encontrados, total_credit)
            
            # Gerar validação de autenticidade
            validacao = validar_autenticidade(dados_declarados, dados_serasa, perfil_gastos)
            
            # Gerar badge independente da validação
            badge_ascii = gerar_badge_ascii(perfil_gastos)
            
            # Gerar dicas educacionais
            dicas_educacionais = gerar_dicas_educacionais(perfil_gastos, validacao)
            
            # Construir mensagens separadas
            mensagem_analise = (
                f"📊 Análise financeira para CPF {cpf}:\n\n"
                f"💵 Total de Créditos: R$ {total_credit:.2f}\n"
                f"💳 Total de Débitos: R$ {sum(d['valor'] for d in debitos_encontrados):.2f}\n\n"
                "📝 Detalhamento dos débitos:\n"
            )
            for debito in debitos_encontrados:
                mensagem_analise += f"- {debito['tipo']}: R$ {debito['valor']:.2f}\n"
            
            mensagem_serasa = "\n🔍 Débitos Serasa:\n"
            for debito in dados_serasa:
                mensagem_serasa += f"- {debito['tipo']}: R$ {debito['valor']:.2f}\n"
            
            mensagem_validacao = f"\n🤖 VALIDAÇÃO:\n{validacao}\n"
            
            mensagem_dicas = f"\n📚 DICAS EDUCACIONAIS:\n{dicas_educacionais}\n"
            
            mensagem_badge = f"\n🏆 SUA BADGE:\n{badge_ascii}\n"
            
            # Enviar mensagens separadamente
            mensagens = [
                mensagem_analise,
                mensagem_serasa,
                mensagem_validacao,
                mensagem_dicas,
                mensagem_badge
            ]
            
            for msg in mensagens:
                if msg.strip():
                    twilio_client.messages.create(
                        from_=TWILIO_PHONE_NUMBER,
                        to=telefone_remetente,
                        body=msg.strip()
                    )
                    print(f"Mensagem enviada: {len(msg)} caracteres")
            
            print("Todas as mensagens enviadas com sucesso!")
            
        return '', 200
            
    except Exception as e:
        print(f"Erro no webhook: {str(e)}")
        return '', 200

@app.route('/test', methods=['GET'])
def test_twilio():
    try:
        # Enviar mensagem de teste
        twilio_client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to="whatsapp:+5511966477946",  # Seu número de WhatsApp
            body="Teste de conexão OK!"
        )
        return "Mensagem de teste enviada!", 200
    except Exception as e:
        return f"Erro ao enviar mensagem de teste: {str(e)}", 500

# Rodar a aplicação Flask
if __name__ == "__main__":
    print("ready")
    app.run(port=8080)
