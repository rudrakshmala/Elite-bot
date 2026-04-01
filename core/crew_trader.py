import os
import yfinance as yf
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# --- ⚡ GROQ CLOUD AI SETUP ---
# 1. Paste your Groq API key right here inside the quotes!
# (Note: Be careful sharing this key publicly! Keep it secret in your real environment.)
os.environ["GROQ_API_KEY"] = "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"

# Pointing CrewAI to Groq's blazing-fast Llama 3.3 70B model
groq_llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.1
)

# --- 🛠️ TOOLS ---
@tool("live_stock_data_tool")
def live_stock_data_tool(ticker: str) -> str:
    """Fetches live price and volume for a given stock ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        
        if hist.empty:
            return f"Data currently unavailable for {ticker}."
            
        price = hist['Close'].iloc[-1]
        volume = int(hist['Volume'].iloc[-1])
        
        return f"Ticker: {ticker} | Last Price: ${price:.2f} | Volume: {volume}"
    except Exception as e:
        return f"Error fetching data for {ticker}: {e}"

@tool("market_news_tool")
def market_news_tool(ticker: str) -> str:
    """
    Fetches the most recent financial news for a specific stock ticker.
    Use this to check for earnings reports, lawsuits, or major announcements.
    Input MUST be a single valid stock ticker symbol (e.g., 'V', 'MA').
    """
    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news
        
        if not news_items:
            return f"No recent financial news found for {ticker}."

        news_summary = f"--- Recent News for {ticker} ---\n"
        for item in news_items[:5]: 
            title = item.get('title', 'No Title')
            publisher = item.get('publisher', 'Unknown Publisher')
            link = item.get('link', 'No Link')
            
            news_summary += f"\n📰 **{title}** ({publisher})\n   Link: {link}\n"
            
        return news_summary

    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}."

# --- 🤖 AGENTS ---
# The Optimist (legacy; uses Groq like the rest)
bull_analyst = Agent(
    role='Bullish Research Lead',
    goal='Argue FOR the execution of the {ticker_1}/{ticker_2} pair trade.',
    backstory="""You are an expert at identifying mean-reversion opportunities. 
    Your job is to prove that the current Z-score of {z_score} is a massive 
    opportunity and that the spread will inevitably close.""",
    verbose=True,
    allow_delegation=False,
    llm=groq_llm
)

# The Skeptic (legacy; uses Groq like the rest)
bear_analyst = Agent(
    role='Bearish Risk Analyst',
    goal='Argue AGAINST the trade and find "hidden traps".',
    backstory="""You are a cynical veteran trader. You assume every signal is 
    a "Value Trap". Your job is to find news or macro reasons why this pair 
    is diverging for a real reason (e.g., a merger, a lawsuit, or a bankruptcy).""",
    verbose=True,
    allow_delegation=False,
    llm=groq_llm
)
quant_agent = Agent(
    role='Senior Quantitative Analyst',
    goal='Analyze live price and volume data to confirm mean-reversion setups.',
    backstory='You are a master of statistical arbitrage and quantitative finance.',
    verbose=True,
    allow_delegation=False,
    tools=[live_stock_data_tool],
    llm=groq_llm  
)

analyst_agent = Agent(
    role='Head of Fundamental & Sentiment Analysis',
    goal='Check for breaking news, earnings reports, or impending catalysts that could break a correlation.',
    backstory='You are an expert at identifying risk and fundamental shifts in the market.',
    verbose=True,
    allow_delegation=False,
    tools=[market_news_tool],
    llm=groq_llm  
)

bear_analyst_agent = Agent(
    role='Bear Analyst',
    goal='Find concrete reasons NOT to trade the pair: overvaluation, weak volume, negative catalysts, correlation breakdown risks, or unfavorable risk/reward.',
    backstory='You are a skeptical contrarian who always looks for the downside. Your job is to challenge every trade and surface risks others might miss.',
    verbose=True,
    allow_delegation=False,
    tools=[live_stock_data_tool, market_news_tool],
    llm=groq_llm
)

cio_agent = Agent(
    role='Chief Investment Officer',
    goal='Make the final TRADE or SKIP decision by weighing quant data, news summaries, and the Bear Analyst\'s objections. Output strict JSON only.',
    backstory='You are a ruthless hedge fund manager who only takes high-probability mean-reversion trades. You must always consider the Bear Analyst\'s concerns before approving any trade. You output strict JSON.',
    verbose=True,
    allow_delegation=False,
    llm=groq_llm  
)

# --- 🚀 EXECUTION ENGINE ---
def evaluate_opportunity(sym_a, sym_b, z_score):
    print(f"\n📢 Assembling the Crew to evaluate {sym_a}/{sym_b} (Z: {z_score})")

    task_quant = Task(
        description=f'Use your tool to check the live price and volume for {sym_a} and {sym_b}. The current Z-score is {z_score}. Write a brief summary on whether the live data supports a mean-reversion trade.',
        expected_output='A brief summary of live price and volume data, and whether it supports a trade.',
        agent=quant_agent
    )

    task_news = Task(
        description=f'''Use your market_news_tool to search for recent financial news for the tickers {sym_a} and {sym_b}. 
        CRITICAL: You must use the tool twice—once for {sym_a} and once for {sym_b}. 
        Are there impending earnings reports, lawsuits, or major announcements that make this trade dangerous?''',
        expected_output='A summary of any recent news or catalysts for both stocks, and an assessment of the fundamental risk.',
        agent=analyst_agent
    )

    task_bear = Task(
        description=f'''Use your tools to find reasons NOT to trade {sym_a}/{sym_b}. 
        Check live price/volume for both tickers and news for both. Look for: thin volume, negative catalysts, 
        stretched valuations, correlation breakdown risks, or any factor that argues AGAINST this mean-reversion setup.
        Be thorough and skeptical—your job is to find what could go wrong.''',
        expected_output='A concise list of bearish concerns and reasons to skip this trade.',
        agent=bear_analyst_agent
    )

    task_cio = Task(
        description=f'''You are the final decision maker. Review the Quant's math, the Analyst's news summary, 
        and CRITICALLY the Bear Analyst's concerns for {sym_a} vs {sym_b}. 
        You MUST weigh the Bear Analyst's objections before deciding.
        
        Direction: Z-score is {z_score}. Negative Z means the spread is cheap → mean reversion = BUY. Positive Z means the spread is expensive → mean reversion = SELL. Only output BUY or SELL if you approve the trade; otherwise output WAIT.
        
        Your output MUST be a valid JSON object only—no extra text, no markdown. Use this exact schema:
        {{
            "signal_strength": 0.0 to 1.0,
            "confidence": 0 to 100,
            "bull_case_summary": "1-2 sentences summarizing why this trade could work",
            "bear_case_summary": "1-2 sentences summarizing the main risks and Bear Analyst concerns",
            "final_action": "BUY" or "SELL" or "WAIT"
        }}''',
        expected_output='A strict JSON object with signal_strength, confidence, bull_case_summary, bear_case_summary, and final_action.',
        agent=cio_agent,
        context=[task_quant, task_news, task_bear]
    )

    trading_crew = Crew(
        agents=[quant_agent, analyst_agent, bear_analyst_agent, cio_agent],
        tasks=[task_quant, task_news, task_bear, task_cio],
        process=Process.sequential,
        verbose=True
    )

    result = trading_crew.kickoff()
    return result