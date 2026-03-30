import firebase_admin
from firebase_admin import credentials, firestore
import yfinance as yf
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

for doc in docs:
    user_data = doc.to_dict()
    if not user_data:
        continue
        
    # 🌟 防彈衣：強制檢查並轉換，拒絕 NoneType 攻擊
    market_prices = user_data.get("marketPrices")
    if not isinstance(market_prices, dict):
        market_prices = {}
        
    stock_names = user_data.get("stockNames")
    if not isinstance(stock_names, dict):
        stock_names = {}
    
    if not market_prices:
        print(f"用戶 {doc.id} 沒有持倉數據，跳過。")
        continue
    
    updated_prices = {}
    updated_names = stock_names.copy()
    updated_count = 0
    
    print(f"正在更新用戶: {doc.id} 的報價與名稱...")
    for symbol_str, old_price in market_prices.items():
        # 再次防彈：確保 symbol 係字串
        if not isinstance(symbol_str, str):
            continue
            
        ticker = symbol_str.split(' ')[0] 
        if ticker.startswith('HKG:'):
            ticker = ticker.replace('HKG:', '') + '.HK'
            
        try:
            stock = yf.Ticker(ticker)
            
            # 獲取最新價錢
            hist = stock.history(period="1d")
            if not hist.empty:
                latest_price = float(hist['Close'].iloc[-1])
            else:
                latest_price = float(stock.fast_info.get('lastPrice', old_price or 0))
                
            # 獲取官方股票名稱
            info = stock.info
            company_name = info.get('shortName') or info.get('longName') or ticker
            
            updated_prices[symbol_str] = round(latest_price, 2)
            updated_names[ticker] = company_name 
            
            updated_count += 1
            print(f"  - {ticker} ({company_name}) 更新成功: ${latest_price:.2f}")
        except Exception as e:
            print(f"  - {ticker} 更新失敗 ({e})，保留舊資料")
            updated_prices[symbol_str] = old_price
            
    # 4. 將最新價格、名稱字典與時間寫回 Firebase
    doc.reference.update({
        "marketPrices": updated_prices,
        "stockNames": updated_names, 
        "lastUpdatedTime": update_time
    })
    print(f"完成！用戶 {doc.id} 共更新 {updated_count} 隻股票。\n")
