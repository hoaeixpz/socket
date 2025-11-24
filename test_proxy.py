import akshare as ak
import requests
import random
import time
import os
from fake_useragent import UserAgent

class HybridProxyCrawler:
    def __init__(self, proxy_list=None):
        self.ua = UserAgent()
        self.proxy_list = proxy_list or [
            'http://127.0.0.1:7890'  # 你的代理地址
        ]
        self.request_count = 0
        self.setup_session()
    
    def setup_session(self, use_proxy=None):
        """设置会话，随机决定是否使用代理"""
        self.request_count += 1
        
        # 🎯 策略1：随机决定（70%不用代理，30%用代理）
        #if use_proxy is None:
        #    use_proxy = random.random() < 0.3
        
        # 🎯 策略2：每N次请求切换一次
        if self.request_count % 2 == 0:
            use_proxy = True
        else:
            use_proxy = False
        
        if use_proxy:
            # 使用代理
            proxy = random.choice(self.proxy_list)
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy
            print(f"🔀 使用代理: {proxy}")
        else:
            # 不用代理（清除代理设置）
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            print("🏠 使用直连")
        
        # 设置真实的请求头
        self.setup_realistic_headers()
        
        return use_proxy
    
    def setup_realistic_headers(self):
        """设置真实的浏览器请求头"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        ak.session = session
    
    def smart_delay(self):
        """智能延迟"""
        # 用代理时延迟短一些（代理服务器通常较慢）
        current_proxy = os.environ.get('HTTP_PROXY')
        if current_proxy:
            delay = random.uniform(20, 30)  # 代理模式延迟短
        else:
            delay = random.uniform(30, 40)  # 直连模式延迟长
        
        print(f"⏳ 等待 {delay:.1f} 秒...")
        time.sleep(delay)
    
    def fetch_data(self, symbol, force_proxy=None):
        """获取数据，可强制指定是否用代理"""
        use_proxy = self.setup_session(use_proxy=force_proxy)
        
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily")
            print(f"✅ 成功获取 {symbol}")
            return df
        except Exception as e:
            print(f"❌ 获取失败: {e}")
            
            # 失败时切换模式重试
            print("🔄 切换模式重试...")
            use_proxy = not use_proxy  # 切换代理/直连模式
            self.setup_session(use_proxy=use_proxy)
            
            try:
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily")
                print(f"✅ 重试成功获取 {symbol}")
                return df
            except Exception as e2:
                print(f"❌ 重试也失败: {e2}")
                raise e2
        finally:
            self.smart_delay()

# 使用示例
#crawler = HybridProxyCrawler()

#stocks = ["000001", "000002"]
#for stock in stocks:
#    print(f"\n📈 获取股票 {stock}")
#    df = crawler.fetch_data(stock)
#    print(f"   数据形状: {df.shape}")