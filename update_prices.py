import firebase_admin
from firebase_admin import credentials, firestore
import requests
import os
import json
from datetime import datetime
import pytz

# 1. 讀取鎖匙並寫入實體檔案
cert_json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
if not cert_json_str:
    raise ValueError("找不到 FIREBASE_SERVICE_ACCOUNT 鎖匙！")

with open("firebase_key.json", "w", encoding="utf-8") as f:
    f.write(cert_json_str)

cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 2. 獲取香港時間
hk_tz = pytz.timezone('Asia/Hong_Kong')
update_time = datetime.now(hk_tz).strftime('%Y-%m-%d %H:%M:%S (自動更新)')

# 3. 掃描所有用戶
users_ref = db.collection("users")
docs = users_ref.stream()

# 🌟 偽裝成普通瀏覽器，完美繞過 Yahoo 封鎖
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

for doc in docs:
    user_data = doc.to_dict()
    if not user_data: continue
        
    market_prices = user_data.get("marketPrices")
    if not isinstance(market_prices, dict): market_prices = {}
        
    stock_names = user_data.get("stockNames")
    if not isinstance(stock_names, dict): stock_names = {}
    
    if not market_prices:
        continue
    
    updated_prices = {}
    updated_names = stock_names.copy()
    updated_count = 0
    
    print(f"正在更新用戶: {doc.id} 的報價與名稱...")
    for symbol_str, old_price in market_prices.items():
        if not isinstance(symbol_str, str): continue
            
        ticker = symbol_str.split(' ')[0] 
        if ticker.startswith('HKG:'):
            ticker = ticker.replace('HKG:', '') + '.HK'
            
        try:
            # 🌟 放棄 yfinance，直接呼叫 Yahoo 原生 API 獲取名稱與價錢
            url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            result = data.get('quoteResponse', {}).get('result', [])
            
            if result:
                quote = result[0]
                latest_price = quote.get('regularMarketPrice', old_price)
                
                # 🌟 完美提取官方名稱 (例如: 騰訊控股)
                company_name = quote.get('shortName') or quote.get('longName') or ticker
                
                updated_prices[symbol_str] = round(latest_price, 2)
                updated_names[ticker] = company_name 
                
                updated_count += 1
                print(f"  - {ticker} ({company_name}) 更新成功: ${latest_price:.2f}")
            else:
                raise ValueError("API 回傳空數據")
                
        except Exception as e:
            print(f"  - {ticker} 更新失敗 ({e})，保留舊資料")
            updated_prices[symbol_str] = old_price
            
    # 4. 寫回 Firebase
    doc.reference.update({
        "marketPrices": updated_prices,
        "stockNames": updated_names, 
        "lastUpdatedTime": update_time
    })
    print(f"完成！用戶 {doc.id} 共更新 {updated_count} 隻股票。\n")
