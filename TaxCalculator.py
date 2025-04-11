'''
Calculate applicable capitals gains taxes
from Cash app bitcoin csv transaction data
after processing transactions in load_transactions.

Adjust any csv file heading labels for use with 
other sources. Script can be called from the cmd
prompt with several args to modify headings as well.

The required argument specifies input csv file, and
an output file will be written in working directory
"Bitcoin-Capital-Gains.csv" containing each taxable
event and required tax reporting details.
'''
import csv
from sys import argv
from datetime import datetime

# CSV File
csv_input_path = 'bitcoin_transactions.csv'
csv_output_path = 'Bitcoin-Capital-Gains.csv'

# Tax rates
SHORT_TERM_TAX_RATE = 0.24
LONG_TERM_TAX_RATE = 0.15
MAX_CAPITAL_LOSS_DEDUCTION = 3000.00  # USD

# CSV file headings
DATE_HEADER = 'DATE'
TRANSACTION_TYPE_HEADER = 'TYPE'
AMOUNT_BITCOIN_HEADER = 'AMT-BTC'
PRICE_DOLLARS_HEADER = 'PRICE'
FEES_HEADER = 'FEE'
DATE_FMT_STRING = '%m-%d-%YYYY'
TRANSACTION_BUY = 'BUY'
TRANSACTION_SELL = 'SALE'

# Parse date
def parse_date(date_str):
    return datetime.strptime(date_str, DATE_FMT_STRING)

# Load transactions
def load_transactions(csv_path):
    transactions = []
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tx = {
                'date': parse_date(row[DATE_HEADER]),
                'type': row[TRANSACTION_TYPE_HEADER].upper(),
                'amount': float(row[AMOUNT_BITCOIN_HEADER]),
                'price': float(row[PRICE_DOLLARS_HEADER]),
                'fees': float(row[FEES_HEADER]),
            }
            transactions.append(tx)
    return sorted(transactions, key=lambda x: x['date'])

# FIFO lot tracking and tax calculation
def calculate_gains(transactions):
    lots = []  # active holdings
    realized = []

    for tx in transactions:
        if tx['type'] == TRANSACTION_BUY:
            lots.append({
                'amount': tx['amount'],
                'price': tx['price'],
                'date': tx['date'],
                'fees': tx['fees']
            })
        elif tx['type'] == TRANSACTION_SELL:
            amount_to_sell = tx['amount']
            sell_price = tx['price']
            sell_date = tx['date']
            sell_fees = tx['fees']

            while amount_to_sell > 0 and lots:
                lot = lots[0]
                amount_from_lot = min(amount_to_sell, lot['amount'])

                cost_basis = amount_from_lot * lot['price']
                proceeds = amount_from_lot * sell_price
                gain = proceeds - cost_basis

                # Pro-rated fees
                gain -= sell_fees * (amount_from_lot / tx['amount'])
                gain -= lot['fees'] * (amount_from_lot / lot['amount'])

                holding_period_days = (sell_date - lot['date']).days
                long_term = holding_period_days > 365
                tax_rate = LONG_TERM_TAX_RATE if long_term else SHORT_TERM_TAX_RATE
                tax_owed = gain * tax_rate if gain > 0 else 0.0

                realized.append({
                    'sell_date': sell_date,
                    'buy_date': lot['date'],
                    'amount': round(amount_from_lot, 8),
                    'cost_basis': round(cost_basis, 2),
                    'proceeds': round(proceeds, 2),
                    'gain': round(gain, 2),
                    'holding_days': holding_period_days,
                    'term': 'Long' if long_term else 'Short',
                    'tax_rate': tax_rate,
                    'tax_owed': round(tax_owed, 2)
                })

                lot['amount'] -= amount_from_lot
                if lot['amount'] == 0:
                    lots.pop(0)
                amount_to_sell -= amount_from_lot

    return realized

# Summary and output
def summarize_gains(gains):
    st_gain, st_loss, lt_gain, lt_loss, total_tax = 0, 0, 0, 0, 0

    print('Sell Date | Buy Date | Amount | Cost Basis | Proceeds | Gain/Loss | Term | Holding Days | Tax Rate | Tax Owed')
    for g in gains:
        print(f"{g['sell_date'].date()} | {g['buy_date'].date()} | {g['amount']} | ${g['cost_basis']} | ${g['proceeds']} | ${g['gain']} | {g['term']} | {g['holding_days']} | {int(g['tax_rate']*100)}% | ${g['tax_owed']}")
        
        if g['term'] == 'Short':
            if g['gain'] >= 0:
                st_gain += g['gain']
            else:
                st_loss += g['gain']
        else:
            if g['gain'] >= 0:
                lt_gain += g['gain']
            else:
                lt_loss += g['gain']
        
        total_tax += g['tax_owed']

    net_gain = st_gain + lt_gain + st_loss + lt_loss
    net_loss = st_loss + lt_loss
    deductible_loss = min(abs(net_loss), MAX_CAPITAL_LOSS_DEDUCTION) if net_gain < 0 else 0.0

    print('\n--- SUMMARY ---')
    print(f"Total Short-Term Gains: ${st_gain:,.2f}")
    print(f"Total Short-Term Losses: ${st_loss:,.2f}")
    print(f"Total Long-Term Gains: ${lt_gain:,.2f}")
    print(f"Total Long-Term Losses: ${lt_loss:,.2f}")
    print(f"Net Gain/Loss: ${net_gain:,.2f}")
    print(f"Capital Loss Deduction (max ${MAX_CAPITAL_LOSS_DEDUCTION:,.2f}): ${deductible_loss:,.2f}")
    print(f"Final Tax Owed (on gains only): ${total_tax:,.2f}")

if __name__ == '__main__':
    transactions = load_transactions(csv_input_path)
    realized = calculate_gains(transactions)
    summarize_gains(realized)

    # Output csv file
    with open(csv_output_path, newline='', mode='w') as csvfile:
        if realized:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=realized,
                restval=''
            )
            writer.writeheader()
            writer.writerows(realized)
