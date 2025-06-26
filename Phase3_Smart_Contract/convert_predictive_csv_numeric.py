import csv
from decimal import Decimal, getcontext, ROUND_HALF_UP

# تنظیم دقت محاسبات اعشاری
getcontext().prec = 50  # دقت کافی برای محاسبات Uniswap V3

# اعشار توکن‌ها
TOKEN0_DECIMALS = 6   # USDC
TOKEN1_DECIMALS = 18  # WETH

# ثابت‌های Uniswap V3
Q96 = Decimal(2**96)
TICK_BASE = Decimal('1.0001')

def sqrt_price_x96_to_price_token1_in_token0(sqrt_price_x96_str: str) -> Decimal:
    """
    محاسبه قیمت token1 بر حسب token0 از sqrtPriceX96
    برای استخر USDC/WETH: قیمت WETH بر حسب USDC (مثلاً 2634.12 USDC برای 1 WETH)
    """
    if not sqrt_price_x96_str or sqrt_price_x96_str.strip() == "":
        return None
    
    try:
        sqrt_price_x96 = Decimal(sqrt_price_x96_str)
        if sqrt_price_x96 == 0:
            return Decimal(0)
        
        # محاسبه قیمت token1 بر حسب token0
        price = (sqrt_price_x96 / Q96) ** 2
        
        # تنظیم اعشار
        decimals_adjustment = Decimal(10) ** (TOKEN1_DECIMALS - TOKEN0_DECIMALS)
        return price / decimals_adjustment
    except Exception as e:
        print(f"Error converting sqrtPriceX96: {e}")
        return None

def sqrt_price_x96_to_price_token0_in_token1(sqrt_price_x96_str: str) -> Decimal:
    """
    محاسبه قیمت token0 بر حسب token1 از sqrtPriceX96
    برای استخر USDC/WETH: قیمت USDC بر حسب WETH (مثلاً 0.00038 WETH برای 1 USDC)
    """
    if not sqrt_price_x96_str or sqrt_price_x96_str.strip() == "":
        return None
    
    try:
        sqrt_price_x96 = Decimal(sqrt_price_x96_str)
        if sqrt_price_x96 == 0:
            return Decimal(0)
        
        # محاسبه قیمت token0 بر حسب token1
        price_t1_in_t0 = (sqrt_price_x96 / Q96) ** 2
        if price_t1_in_t0 == 0:
            return None
        
        price_t0_in_t1 = Decimal(1) / price_t1_in_t0
        
        # تنظیم اعشار
        decimals_adjustment = Decimal(10) ** (TOKEN0_DECIMALS - TOKEN1_DECIMALS)
        return price_t0_in_t1 / decimals_adjustment
    except Exception as e:
        print(f"Error converting sqrtPriceX96 (inverse): {e}")
        return None

def tick_to_price_token1_in_token0(tick_str: str) -> Decimal:
    """
    تبدیل تیک به قیمت token1 بر حسب token0
    برای استخر USDC/WETH: قیمت WETH بر حسب USDC
    """
    if not tick_str or tick_str.strip() == "":
        return None
    
    try:
        tick = int(Decimal(tick_str))
        price = TICK_BASE ** Decimal(tick)
        
        # تنظیم اعشار
        decimals_adjustment = Decimal(10) ** (TOKEN1_DECIMALS - TOKEN0_DECIMALS)
        return price / decimals_adjustment
    except Exception as e:
        print(f"Error converting tick: {e}")
        return None

def tick_to_price_token0_in_token1(tick_str: str) -> Decimal:
    """
    تبدیل تیک به قیمت token0 بر حسب token1
    برای استخر USDC/WETH: قیمت USDC بر حسب WETH
    """
    if not tick_str or tick_str.strip() == "":
        return None
    
    try:
        tick = int(Decimal(tick_str))
        price_t1_in_t0 = TICK_BASE ** Decimal(tick)
        if price_t1_in_t0 == 0:
            return None
        
        price_t0_in_t1 = Decimal(1) / price_t1_in_t0
        
        # تنظیم اعشار
        decimals_adjustment = Decimal(10) ** (TOKEN0_DECIMALS - TOKEN1_DECIMALS)
        return price_t0_in_t1 / decimals_adjustment
    except Exception as e:
        print(f"Error converting tick (inverse): {e}")
        return None

def format_decimal(value: Decimal, precision: int = 6) -> str:
    """
    فرمت دهی اعداد اعشاری برای نمایش بهتر
    """
    if value is None:
        return ""
    
    if value == Decimal(0):
        return "0"
    
    # نمایش علمی برای اعداد خیلی بزرگ یا کوچک
    if abs(value) < Decimal('0.0001') or abs(value) > Decimal('1000000'):
        return f"{value:.{precision}e}"
    
    # نمایش معمولی با حذف صفرهای غیرضروری
    return f"{value:.{precision}f}".rstrip('0').rstrip('.') if '.' in f"{value}" else f"{value}"

def process_csv(input_path: str, output_path: str):
    """
    پردازش فایل CSV و ایجاد فایل خروجی با مقادیر تبدیل شده
    """
    with open(input_path, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        # فیلدهای جدید برای خروجی
        new_fields = fieldnames + [
            'price_WETH_in_USDC',  # قیمت WETH بر حسب USDC (مثلاً 2634.12)
            'price_USDC_in_WETH',  # قیمت USDC بر حسب WETH (مثلاً 0.00038)
            'tick_to_price_WETH_in_USDC',  # قیمت WETH بر حسب USDC از تیک
            'tick_to_price_USDC_in_WETH',  # قیمت USDC بر حسب WETH از تیک
            'price_difference'  # اختلاف قیمت با قیمت خارجی
        ]
        
        rows = []
        for row in reader:
            # محاسبه قیمت از sqrtPriceX96
            sqrt_price = row.get('sqrtPriceX96_pool', '')
            price_weth_in_usdc = sqrt_price_x96_to_price_token1_in_token0(sqrt_price)
            price_usdc_in_weth = sqrt_price_x96_to_price_token0_in_token1(sqrt_price)
            
            row['price_WETH_in_USDC'] = format_decimal(price_weth_in_usdc) if price_weth_in_usdc is not None else ""
            row['price_USDC_in_WETH'] = format_decimal(price_usdc_in_weth) if price_usdc_in_weth is not None else ""
            
            # محاسبه قیمت از تیک جاری
            current_tick = row.get('currentTick_pool', '')
            tick_price_weth_in_usdc = tick_to_price_token1_in_token0(current_tick)
            tick_price_usdc_in_weth = tick_to_price_token0_in_token1(current_tick)
            
            row['tick_to_price_WETH_in_USDC'] = format_decimal(tick_price_weth_in_usdc) if tick_price_weth_in_usdc is not None else ""
            row['tick_to_price_USDC_in_WETH'] = format_decimal(tick_price_usdc_in_weth) if tick_price_usdc_in_weth is not None else ""
            
            # محاسبه اختلاف قیمت
            try:
                external_price = Decimal(row.get('external_api_eth_price', 0))
                if external_price != 0 and price_weth_in_usdc is not None:
                    difference = (price_weth_in_usdc - external_price) / external_price * 100
                    row['price_difference'] = f"{difference:.2f}%"
                else:
                    row['price_difference'] = ""
            except:
                row['price_difference'] = ""
            
            # تبدیل تیک‌های دیگر به قیمت
            for tick_field in ['predictedTick_calculated', 'targetTickLower_calculated', 'targetTickUpper_calculated', 
                              'finalTickLower_contract', 'finalTickUpper_contract']:
                if tick_field in row and row[tick_field]:
                    tick_value = row[tick_field]
                    price = tick_to_price_token1_in_token0(tick_value)
                    if price is not None:
                        row[f"{tick_field}_price"] = format_decimal(price)
            
            rows.append(row)
    
    # ذخیره فایل خروجی
    with open(output_path, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=new_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

# اجرای اسکریپت
if __name__ == "__main__":
    input_files = [
        ('position_results_predictive.csv', 'predictive_converted.csv'),
        ('position_results_baseline.csv', 'baseline_converted.csv')
    ]
    
    for input_file, output_file in input_files:
        print(f"Processing {input_file}...")
        try:
            process_csv(input_file, output_file)
            print(f"Successfully converted to {output_file}")
        except Exception as e:
            print(f"Error processing {input_file}: {e}")