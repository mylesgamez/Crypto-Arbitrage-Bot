import ccxt
import time
import logging
import os

# Initialize the logging system
logging.basicConfig(filename='arb_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 1. Configurations and Secrets
API_KEYS = {
    "binance": {
        "apiKey": os.environ["BINANCE_API_KEY"],
        "secret": os.environ["BINANCE_API_SECRET"]
    },
    "coinbasepro": {
        "apiKey": os.environ["COINBASE_PRO_API_KEY"],
        "secret": os.environ["COINBASE_PRO_API_SECRET"]
    }
}

# 2. Dynamic Exchange Initialization
exchanges = {}
for exchange_name, credentials in API_KEYS.items():
    exchanges[exchange_name] = getattr(ccxt, exchange_name)(credentials)

# Define the trading pairs
symbols = ['BTC/USDT', 'ADA/USDT', 'ETH/USDT',
           'DOGE/USDT', 'LTC/USDT', 'XRP/USDT']

# Define your trading parameters
trade_amount = 0.1
profit_threshold = 0.5
trailing_stop_percentage = 2.0

highest_prices = {symbol: None for symbol in symbols}
buy_orders = {}
sell_orders = {}

max_errors = 5
error_count = 0

# Placeholder for trading fees (in percentage)
TRADING_FEES = {
    'binance': 0.1,       # assuming 0.1% fee for Binance
    'coinbasepro': 0.25   # assuming 0.25% fee for Coinbase Pro
}


def log_info(message):
    logging.info(message)
    print(message)


def log_error(message):
    global error_count
    error_count += 1
    if error_count >= max_errors:
        log_info("Circuit breaker triggered. Halting trading.")
        time.sleep(3600)
    logging.error(message)
    print(f"ERROR: {message}")


def reset_circuit_breaker():
    global error_count
    error_count = 0


def get_prices(exchanges, symbols):
    prices = {}
    for exchange in exchanges.values():
        for symbol in symbols:
            try:
                ticker = exchange.fetch_ticker(symbol)
                prices[f"{exchange.id} - {symbol}"] = ticker['last']
            except Exception as e:
                log_error(f"Error fetching data from {exchange.id}: {str(e)}")

    return prices


def update_trailing_stop(symbol, current_price):
    global highest_prices
    if symbol in highest_prices:
        if highest_prices[symbol] is None or current_price > highest_prices[symbol]:
            highest_prices[symbol] = current_price
    else:
        highest_prices[symbol] = current_price


def calculate_profit(base_price, comp_price, buy_exchange_name, sell_exchange_name):
    """Calculate profit after considering trading fees."""
    buy_fee = TRADING_FEES[buy_exchange_name] / 100
    sell_fee = TRADING_FEES[sell_exchange_name] / 100

    effective_buy_price = comp_price * (1 + buy_fee)
    effective_sell_price = base_price * (1 - sell_fee)

    profit_percentage = (
        (effective_sell_price - effective_buy_price) / effective_buy_price) * 100

    return profit_percentage


def execute_trade(buy_exchange, sell_exchange, symbol, amount, trailing_stop_percentage):
    try:
        # Define buy and sell orders
        buy_order = buy_exchange.create_limit_buy_order(
            symbol, amount, buy_price)
        sell_order = sell_exchange.create_limit_sell_order(
            symbol, amount, sell_price)

        # Store order IDs in the respective dictionaries
        buy_orders[symbol] = buy_order['id']
        sell_orders[symbol] = sell_order['id']

        log_info(f"Buy order ID: {buy_order['id']}")
        log_info(f"Sell order ID: {sell_order['id']}")
        log_info(
            f"Successfully executed arbitrage trade on {buy_exchange.id} and {sell_exchange.id}.")

        # Implement trailing stop
        current_sell_price = sell_order['price']
        update_trailing_stop(symbol, current_sell_price)
        trailing_stop_price = highest_prices[symbol] * \
            (1 - trailing_stop_percentage / 100)

        # Continuously check if the trailing stop is triggered
        while current_sell_price > trailing_stop_price:
            time.sleep(1)  # Adjust the interval as needed
            current_sell_price = sell_exchange.fetch_order(sell_orders[symbol])[
                'price']
            if current_sell_price > trailing_stop_price:
                log_info("Trailing stop activated. Selling position.")
                sell_order = sell_exchange.create_market_sell_order(
                    symbol, amount)

    except Exception as e:
        error_message = f"Error executing trade: {str(e)}"
        log_error(error_message)


while True:
    try:
        reset_circuit_breaker()
        prices = get_prices(exchanges, symbols)
        log_info(prices)

        for symbol in symbols:
            for ref_exchange_name, ref_exchange in exchanges.items():
                base_price = prices.get(f"{ref_exchange_name} - {symbol}")
                if not base_price:
                    continue

                for comp_exchange_name, comp_exchange in exchanges.items():
                    if comp_exchange_name == ref_exchange_name:
                        continue

                    comp_price = prices.get(f"{comp_exchange_name} - {symbol}")
                    if not comp_price:
                        continue

                    profit_percentage = calculate_profit(
                        base_price, comp_price, comp_exchange_name, ref_exchange_name)

                    if profit_percentage >= profit_threshold:
                        log_info(
                            f"Profit opportunity found on {comp_exchange_name} for {symbol} ({profit_percentage}%).")

                        buy_exchange, sell_exchange = (
                            comp_exchange, ref_exchange) if base_price > comp_price else (ref_exchange, comp_exchange)

                        execute_trade(buy_exchange, sell_exchange, symbol, trade_amount,
                                      trailing_stop_percentage, comp_price, base_price)

    except Exception as e:
        log_error(f"Error: {str(e)}")

    time.sleep(5)
