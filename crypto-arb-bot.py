import ccxt
import time
import logging

# Initialize the logging system
logging.basicConfig(filename='arb_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize exchanges and provide your API keys and secrets
binance = ccxt.binance({
    'apiKey': 'YOUR_BINANCE_API_KEY',
    'secret': 'YOUR_BINANCE_API_SECRET',
})
coinbasepro = ccxt.coinbasepro({
    'apiKey': 'YOUR_COINBASE_PRO_API_KEY',
    'secret': 'YOUR_COINBASE_PRO_API_SECRET',
})
# Add credentials for other exchanges similarly

# Define the trading pairs
symbols = ['BTC/USDT', 'ADA/USDT', 'ETH/USDT', 'DOGE/USDT']

# Define your trading parameters
trade_amount = 0.1  # The amount to trade in the base currency
profit_threshold = 0.5  # Minimum profit percentage to execute a trade
trailing_stop_percentage = 2.0  # Trailing stop percentage

# Initialize a dictionary to store the highest price for each symbol
highest_prices = {symbol: None for symbol in symbols}

# Initialize dictionaries to keep track of orders and their status
buy_orders = {}
sell_orders = {}

# Define circuit breaker parameters
max_errors = 5
error_count = 0


def log_info(message):
    logging.info(message)
    print(message)


def log_error(message):
    global error_count
    error_count += 1
    if error_count >= max_errors:
        log_info("Circuit breaker triggered. Halting trading.")
        time.sleep(3600)  # Sleep for an hour as a circuit breaker
    logging.error(message)
    print(f"ERROR: {message}")


def reset_circuit_breaker():
    global error_count
    error_count = 0


def get_prices(exchanges, symbols):
    prices = {}
    for exchange in exchanges:
        for symbol in symbols:
            try:
                ticker = exchange.fetch_ticker(symbol)
                prices[f"{exchange.id} - {symbol}"] = ticker['last']
            except Exception as e:
                error_message = f"Error fetching data from {exchange.id}: {str(e)}"
                log_error(error_message)
                print(error_message)

    return prices


def update_trailing_stop(symbol, current_price):
    global highest_prices
    if symbol in highest_prices:
        if highest_prices[symbol] is None or current_price > highest_prices[symbol]:
            highest_prices[symbol] = current_price
    else:
        highest_prices[symbol] = current_price


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
        # Choose exchanges for price comparison
        prices = get_prices([binance, coinbasepro], symbols)
        log_info(prices)

        for symbol in symbols:
            base_symbol, quote_symbol = symbol.split('/')
            # Example: use Binance's prices as reference
            base_price = prices[f"binance - {symbol}"]

            # Look for arbitrage opportunities
            for exchange in [coinbasepro]:
                if exchange.id == 'binance':
                    continue  # Skip the reference exchange
                if f"{exchange.id} - {symbol}" not in prices:
                    continue  # Skip if data is missing

                exchange_price = prices[f"{exchange.id} - {symbol}"]
                profit_percentage = (
                    (base_price - exchange_price) / exchange_price) * 100

                if profit_percentage >= profit_threshold:
                    log_info(
                        f"Profit opportunity found on {exchange.id} for {symbol} ({profit_percentage}%).")

                    # Execute the trade here (e.g., buy on Binance, sell on Coinbase Pro)
                    buy_price = exchange_price  # Set the buy price to the current exchange price
                    execute_trade(binance, exchange, symbol,
                                  trade_amount, trailing_stop_percentage)

    except Exception as e:
        error_message = f"Error: {str(e)}"
        log_error(error_message)

    # You may want to introduce a delay to avoid making too many API requests
    time.sleep(5)
