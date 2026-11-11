"""
中国裁判文书网自动化采集程序 - Playwright版本（支持断点续传）
需要安装: pip install playwright pandas playwright-stealth
安装后运行: playwright install chromium
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import pandas as pd
import time
from datetime import datetime
import os
import random
import json

class CourtDocumentScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.data = []
        self.progress_file = "scraper_progress.json"
        self.progress = {
            'current_keyword': None,
            'current_keyword_index': 0,
            'current_page': 1,
            'current_doc_index': 0,
            'keywords': [],
            'completed_keywords': [],
            'last_update': None
        }
        
    def load_progress(self):
        """加载进度文件"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.progress = json.load(f)
                print(f"✓ 已加载进度文件: {self.progress_file}")
                print(f"  上次中断: {self.progress.get('last_update', 'N/A')}")
                print(f"  当前关键词: {self.progress.get('current_keyword', 'N/A')}")
                print(f"  当前页码: {self.progress.get('current_page', 1)}")
                print(f"  当前文书索引: {self.progress.get('current_doc_index', 0)}")
                return True
            except Exception as e:
                print(f"✗ 加载进度文件失败: {e}")
                return False
        return False
    
    def save_progress(self):
        """保存进度到JSON文件"""
        try:
            self.progress['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)
            print(f"  💾 进度已保存: {self.progress_file}")
        except Exception as e:
            print(f"  ✗ 保存进度失败: {e}")
    
    def reset_progress(self):
        """重置进度"""
        self.progress = {
            'current_keyword': None,
            'current_keyword_index': 0,
            'current_page': 1,
            'current_doc_index': 0,
            'keywords': [],
            'completed_keywords': [],
            'last_update': None
        }
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)
        print("✓ 进度已重置")
    
    def update_progress(self, keyword=None, page=None, doc_index=None, keyword_index=None):
        """更新进度"""
        if keyword is not None:
            self.progress['current_keyword'] = keyword
        if page is not None:
            self.progress['current_page'] = page
        if doc_index is not None:
            self.progress['current_doc_index'] = doc_index
        if keyword_index is not None:
            self.progress['current_keyword_index'] = keyword_index
        self.save_progress()
    
    def mark_keyword_completed(self, keyword):
        """标记关键词已完成"""
        if keyword not in self.progress['completed_keywords']:
            self.progress['completed_keywords'].append(keyword)
            self.save_progress()
        
    def init_browser(self, headless=False):
        """初始化浏览器 - 增强反检测"""
        self.playwright = sync_playwright().start()
        
        # 启动浏览器，添加反检测参数
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-position=0,0',
                '--ignore-certifcate-errors',
                '--ignore-certifcate-errors-spki-list',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )
        
        # 创建上下文，模拟真实浏览器
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            permissions=['geolocation'],
            geolocation={'latitude': 39.9042, 'longitude': 116.4074},  # 北京坐标
            color_scheme='light',
            extra_http_headers={
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
        )
        
        self.page = self.context.new_page()
        
        # 注入反检测脚本
        self.page.add_init_script("""
            // 覆盖 navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 覆盖 chrome 对象
            window.chrome = {
                runtime: {}
            };
            
            // 覆盖 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // 覆盖 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 覆盖 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
        """)
        
        self.page.set_default_timeout(60000)  # 60秒超时
        
    def random_delay(self, min_sec=1, max_sec=3):
        """随机延迟，模拟人类行为"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
        
    def open_website(self):
        """打开网站并等待用户登录"""
        url = "https://wenshu.court.gov.cn/website/wenshu/181010CARHS5BS3C/index.html"
        print(f"正在打开网站: {url}")
        
        try:
            # 先访问首页，建立 cookies
            self.page.goto("https://wenshu.court.gov.cn", wait_until='networkidle', timeout=60000)
            self.random_delay(2, 4)
            
            # 然后访问目标页面
            self.page.goto(url, wait_until='networkidle', timeout=60000)
            self.random_delay(2, 3)
            
            # 检查是否需要升级浏览器的提示
            try:
                upgrade_text = self.page.locator("text=/请升级|PLEASE UPGRADE/").first
                if upgrade_text.is_visible(timeout=3000):
                    print("\n警告: 检测到浏览器升级提示，正在尝试绕过...")
                    # 刷新页面重试
                    self.page.reload(wait_until='networkidle')
                    self.random_delay(2, 3)
            except:
                pass
            
        except Exception as e:
            print(f"打开网站时出错: {e}")
            print("尝试直接访问...")
        
        print("\n" + "="*60)
        print("请在浏览器中完成登录（如果需要）...")
        print("="*60)
        print("准备好后，在此处输入 'y' 或 'Y' 继续: ")
        
        while True:
            user_input = input().strip().lower()
            if user_input == 'y':
                print("已确认登录，继续执行...")
                self.random_delay(1, 2)
                break
            else:
                print("请输入 'y' 或 'Y' 继续: ")
    
    def search_keyword(self, keyword):
        """搜索关键词"""
        try:
            print(f"\n正在搜索关键词: {keyword}")
            
            # 多种可能的搜索框选择器
            search_selectors = [
                "input[placeholder*='请输入关键词']",
                "input[type='text'][class*='search']",
                "input#searchWord",
                "input[name='searchWord']",
                ".search-input input",
                "input.ant-input"
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible(timeout=5000):
                        search_input = element
                        print(f"找到搜索框（选择器: {selector}）")
                        break
                except:
                    continue
            
            if not search_input:
                print("未找到搜索框")
                self.page.screenshot(path=f"no_search_box_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False
            
            # 清空并输入关键词
            search_input.fill("")
            self.random_delay(0.5, 1)
            search_input.type(keyword, delay=100)  # 模拟打字速度
            self.random_delay(1, 2)
            
            # 多种可能的搜索按钮选择器
            search_button_selectors = [
                "button:has-text('搜索')",
                "button:has-text('查询')",
                "button.search-btn",
                "button[type='submit']",
                ".search-button"
            ]
            
            search_btn = None
            for selector in search_button_selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible(timeout=3000):
                        search_btn = element
                        print(f"找到搜索按钮（选择器: {selector}）")
                        break
                except:
                    continue
            
            if search_btn:
                search_btn.click()
                print("已点击搜索按钮")
            else:
                # 尝试按回车
                search_input.press("Enter")
                print("通过回车键触发搜索")
            
            # 等待搜索结果加载
            self.random_delay(3, 5)
            self.page.wait_for_load_state('networkidle', timeout=30000)
            
            # 检查是否有结果
            try:
                no_result_text = self.page.locator("text=/暂无数据|没有找到|无结果/").first
                if no_result_text.is_visible(timeout=3000):
                    print("搜索无结果")
                    return False
            except:
                pass
            
            print("✓ 搜索成功")
            return True
            
        except Exception as e:
            print(f"搜索关键词时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def navigate_to_page(self, target_page):
        """导航到指定页码"""
        try:
            print(f"正在导航到第 {target_page} 页...")
            
            # 查找页码输入框
            page_input_selectors = [
                "input[class*='page-input']",
                "input[type='number']",
                ".pagination input",
                "input[placeholder*='页']"
            ]
            
            page_input = None
            for selector in page_input_selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible(timeout=3000):
                        page_input = element
                        break
                except:
                    continue
            
            if page_input:
                page_input.fill(str(target_page))
                page_input.press("Enter")
                self.random_delay(3, 5)
                self.page.wait_for_load_state('networkidle', timeout=30000)
                print(f"✓ 已导航到第 {target_page} 页")
                return True
            else:
                print("未找到页码输入框，尝试点击翻页...")
                # 尝试多次点击下一页
                for _ in range(target_page - 1):
                    next_selectors = [
                        "button:has-text('下一页')",
                        "a:has-text('下一页')",
                        ".next-page",
                        "[aria-label='Next']"
                    ]
                    
                    clicked = False
                    for selector in next_selectors:
                        try:
                            next_btn = self.page.locator(selector).first
                            if next_btn.is_visible(timeout=3000) and next_btn.is_enabled():
                                next_btn.click()
                                clicked = True
                                self.random_delay(2, 3)
                                break
                        except:
                            continue
                    
                    if not clicked:
                        print("翻页失败")
                        return False
                
                return True
                
        except Exception as e:
            print(f"导航到页码时出错: {e}")
            return False
    
    def extract_document_info(self, doc_page):
        """从文书详情页提取信息"""
        try:
            # 等待页面加载
            doc_page.wait_for_load_state('networkidle', timeout=30000)
            self.random_delay(2, 3)
            
            data = {
                '案号': 'N/A',
                '法院': 'N/A',
                '案由': 'N/A',
                '当事人': 'N/A',
                '发布日期': 'N/A',
                '浏览次数': 'N/A',
                '文书内容': '',
                'URL': doc_page.url,
                '抓取时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 尝试提取案号
            case_number_selectors = [
                "div:has-text('案号') + div",
                "span:has-text('案号') + span",
                ".case-number",
                "div[class*='case']"
            ]
            
            for selector in case_number_selectors:
                try:
                    element = doc_page.locator(selector).first
                    if element.is_visible(timeout=3000):
                        data['案号'] = element.inner_text().strip()
                        break
                except:
                    continue
            
            # 尝试提取法院
            court_selectors = [
                "div:has-text('法院') + div",
                "span:has-text('法院') + span",
                ".court-name"
            ]
            
            for selector in court_selectors:
                try:
                    element = doc_page.locator(selector).first
                    if element.is_visible(timeout=3000):
                        data['法院'] = element.inner_text().strip()
                        break
                except:
                    continue
            
            # 提取文书内容
            content_selectors = [
                "div[class*='content']",
                "div[id*='content']",
                ".doc-content",
                "div.text-content",
                "pre"
            ]
            
            for selector in content_selectors:
                try:
                    element = doc_page.locator(selector).first
                    if element.is_visible(timeout=5000):
                        content = element.inner_text().strip()
                        if len(content) > 100:  # 确保内容有效
                            data['文书内容'] = content
                            break
                except:
                    continue
            
            # 如果没找到内容，截图保存
            if not data['文书内容']:
                screenshot_path = f"no_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                doc_page.screenshot(path=screenshot_path)
                print(f"    未找到文书内容，已保存截图: {screenshot_path}")
            
            return data
            
        except Exception as e:
            print(f"  提取文书信息时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_documents(self, keyword, max_pages=5, start_page=1, start_doc_index=0):
        """处理文书列表 - 支持从指定页码和文书索引开始，增加刷新重试机制"""
        current_page = start_page
        
        # 如果不是从第一页开始，需要导航到指定页
        if start_page > 1:
            if not self.navigate_to_page(start_page):
                print(f"✗ 无法导航到第 {start_page} 页，从第1页重新开始")
                current_page = 1
                start_doc_index = 0
        
        while current_page <= max_pages:
            print(f"\n{'='*60}")
            print(f"正在处理第 {current_page}/{max_pages} 页")
            print(f"{'='*60}")
            
            # 更新进度：当前页码
            self.update_progress(page=current_page)
            
            # 等待列表加载
            self.random_delay(2, 3)
            
            # 获取当前页的所有文书链接
            link_selectors = [
                "a[class*='doc-link']",
                "a[class*='title']",
                ".doc-item a",
                "div[class*='item'] a",
                "li a"
            ]
            
            link_elements = []
            for selector in link_selectors:
                try:
                    elements = self.page.locator(selector).all()
                    if elements and len(elements) > 0:
                        link_elements = elements
                        print(f"找到 {len(link_elements)} 个文书链接（选择器: {selector}）")
                        break
                except:
                    continue
            
            if not link_elements:
                print("未找到文书链接，尝试刷新...")
                self.page.reload(wait_until='networkidle')
                self.random_delay(2, 3)
                continue
            
            # 处理每个文书链接
            for i in range(start_doc_index, len(link_elements)):
                # 更新进度：当前文书索引
                self.update_progress(doc_index=i)
                
                print(f"\n[{i+1}/{len(link_elements)}] 正在处理文书...")
                
                try:
                    # 重新获取链接（避免过期）
                    link_elements = []
                    for selector in link_selectors:
                        try:
                            elements = self.page.locator(selector).all()
                            if elements and len(elements) > 0:
                                link_elements = elements
                                break
                        except:
                            continue
                    
                    if i >= len(link_elements):
                        print("  链接索引超出范围，跳过")
                        continue
                    
                    link = link_elements[i]
                    
                    # 获取链接文本
                    try:
                        link_text = link.inner_text()
                        print(f"  文书标题: {link_text[:50]}...")
                    except:
                        link_text = "N/A"
                    
                    # 保存当前页面引用
                    temp_page = self.page
                    
                    # 新增：尝试打开新页面，如果超时则刷新一次重试
                    new_page = None
                    retry_count = 0
                    max_retries = 1  # 只刷新一次
                    
                    while retry_count <= max_retries and new_page is None:
                        try:
                            # 点击链接，在新标签页打开
                            print(f"  尝试打开文书页面... (尝试 {retry_count + 1}/{max_retries + 1})")
                            with self.context.expect_page(timeout=30000) as new_page_info:
                                link.click(modifiers=['Control'])  # Ctrl+点击在新标签页打开
                            
                            new_page = new_page_info.value
                            print(f"  ✓ 成功打开新页面")
                            
                        except PlaywrightTimeout:
                            retry_count += 1
                            if retry_count <= max_retries:
                                print(f"  ⚠ 打开页面超时 (30秒)，正在刷新列表页并重试...")
                                # 刷新当前列表页
                                self.page.reload(wait_until='networkidle', timeout=30000)
                                self.random_delay(2, 3)
                                
                                # 重新获取链接元素
                                link_elements = []
                                for selector in link_selectors:
                                    try:
                                        elements = self.page.locator(selector).all()
                                        if elements and len(elements) > 0:
                                            link_elements = elements
                                            break
                                    except:
                                        continue
                                
                                if i >= len(link_elements):
                                    print("  ✗ 刷新后链接索引超出范围，跳过此文书")
                                    break
                                
                                link = link_elements[i]
                            else:
                                print(f"  ✗ 打开页面失败，已尝试 {max_retries + 1} 次，跳过此文书")
                                break
                    
                    # 如果成功打开新页面，则处理文书
                    if new_page is not None:
                        self.random_delay(2, 3)
                        
                        # 提取文书详细信息
                        doc_data = self.extract_document_info(new_page)
                        
                        if doc_data and doc_data.get('文书内容') and len(doc_data.get('文书内容', '')) > 50:
                            doc_data['关键词'] = keyword
                            doc_data['页码'] = current_page
                            doc_data['序号'] = i + 1
                            self.data.append(doc_data)
                            
                            case_no = doc_data.get('案号', 'N/A')
                            content_len = len(doc_data.get('文书内容', ''))
                            print(f"  ✓ 成功提取文书")
                            print(f"    案号: {case_no}")
                            print(f"    内容长度: {content_len} 字符")
                            
                            # 实时保存数据
                            self.save_to_csv(filename=f"temp_data_{datetime.now().strftime('%Y%m%d')}.csv")
                        else:
                            print("  ✗ 提取失败或内容过短")
                            new_page.screenshot(path=f"empty_content_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                        
                        # 关闭新标签页
                        new_page.close()
                    
                    self.page = temp_page
                    
                    # 等待300秒
                    if i < len(link_elements) - 1:
                        wait_time = 300
                        print(f"\n  等待 {wait_time} 秒后继续... (剩余 {len(link_elements) - i - 1} 篇)")
                        
                        # 分段显示倒计时
                        for remaining in range(wait_time, 0, -30):
                            print(f"    还需等待 {remaining} 秒...", end='\r')
                            time.sleep(min(30, remaining))
                        print()
                    
                except Exception as e:
                    print(f"  ✗ 处理文书时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        if new_page:
                            new_page.close()
                    except:
                        pass
                    self.page = temp_page
                    self.save_progress()
                    continue
            
            # 完成当前页后，重置文书索引
            start_doc_index = 0
            
            # 尝试翻页
            if current_page < max_pages:
                try:
                    print("\n尝试翻到下一页...")
                    
                    next_selectors = [
                        "button:has-text('下一页')",
                        "a:has-text('下一页')",
                        ".next-page:not([disabled])",
                        "[aria-label='Next']",
                        "li.next a"
                    ]
                    
                    clicked = False
                    for selector in next_selectors:
                        try:
                            next_btn = self.page.locator(selector).first
                            if next_btn.is_visible(timeout=3000) and next_btn.is_enabled():
                                next_btn.click()
                                clicked = True
                                print("✓ 已点击下一页")
                                self.random_delay(3, 5)
                                self.page.wait_for_load_state('networkidle', timeout=30000)
                                break
                        except:
                            continue
                    
                    if clicked:
                        current_page += 1
                    else:
                        print("未找到下一页按钮或已到最后一页")
                        break
                        
                except Exception as e:
                    print(f"翻页时出错: {e}")
                    break
            else:
                break
    
    def save_to_csv(self, filename=None):
        """保存数据到CSV"""
        if not self.data:
            return
        
        if filename is None:
            filename = f"court_documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        df = pd.DataFrame(self.data)
        
        # 调整列顺序
        columns_order = ['关键词', '页码', '序号', '案号', '法院', '案由', '当事人', 
                        '发布日期', '浏览次数', '文书内容', 'URL', '抓取时间']
        
        columns_order = [col for col in columns_order if col in df.columns]
        df = df[columns_order]
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"  💾 数据已保存: {filename} ({len(self.data)} 条)")
    
    def load_keywords_from_txt(self, txt_file):
        """从TXT文件加载关键词"""
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                keywords = [line.strip() for line in f if line.strip()]
            print(f"从 {txt_file} 加载了 {len(keywords)} 个关键词")
            return keywords
        except Exception as e:
            print(f"读取TXT文件时出错: {e}")
            return []
    
    def run(self, keywords_input, max_pages=5, resume=False):
        """主运行函数 - 支持断点续传"""
        try:
            # 初始化浏览器
            print("正在启动浏览器...")
            self.init_browser(headless=False)
            
            # 打开网站
            self.open_website()
            
            # 处理关键词
            keywords = []
            if keywords_input.endswith('.txt'):
                keywords = self.load_keywords_from_txt(keywords_input)
            else:
                keywords = [keywords_input]
            
            if not keywords:
                print("没有有效的关键词")
                return
            
            # 保存关键词列表到进度
            self.progress['keywords'] = keywords
            
            # 确定起始位置
            start_keyword_index = 0
            start_page = 1
            start_doc_index = 0
            
            if resume and self.progress.get('current_keyword'):
                # 从进度中恢复
                current_keyword = self.progress.get('current_keyword')
                if current_keyword in keywords:
                    start_keyword_index = keywords.index(current_keyword)
                    start_page = self.progress.get('current_page', 1)
                    start_doc_index = self.progress.get('current_doc_index', 0)
                    print(f"\n{'='*60}")
                    print(f"从断点继续:")
                    print(f"  关键词: {current_keyword} ({start_keyword_index + 1}/{len(keywords)})")
                    print(f"  页码: {start_page}")
                    print(f"  文书索引: {start_doc_index}")
                    print(f"{'='*60}\n")
            
            # 处理每个关键词
            for idx in range(start_keyword_index, len(keywords)):
                keyword = keywords[idx]
                
                # 检查是否已完成
                if keyword in self.progress.get('completed_keywords', []):
                    print(f"\n关键词 '{keyword}' 已完成，跳过")
                    continue
                
                print(f"\n{'='*60}")
                print(f"[{idx+1}/{len(keywords)}] 开始处理关键词: {keyword}")
                print(f"{'='*60}")
                
                # 更新当前关键词
                self.update_progress(keyword=keyword, keyword_index=idx, page=1, doc_index=0)
                
                if self.search_keyword(keyword):
                    # 如果是续传且是当前关键词，使用保存的页码和索引
                    if resume and idx == start_keyword_index:
                        self.process_documents(keyword, max_pages, start_page, start_doc_index)
                        # 用过一次后重置
                        resume = False
                    else:
                        self.process_documents(keyword, max_pages)
                    
                    # 标记关键词已完成
                    self.mark_keyword_completed(keyword)
                else:
                    print(f"关键词 '{keyword}' 搜索失败，跳过")
                
                if idx < len(keywords) - 1:
                    print("\n等待5秒后处理下一个关键词...")
                    time.sleep(5)
            
            # 最终保存
            final_filename = f"court_documents_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.save_to_csv(final_filename)
            
            print("\n" + "="*60)
            print("✓ 程序执行完毕！")
            print(f"✓ 共采集 {len(self.data)} 条记录")
            print("="*60)
            
            # 完成后清理进度文件
            print("\n是否清除进度文件？(y/n): ")
            try:
                if input().strip().lower() == 'y':
                    self.reset_progress()
            except:
                pass
            
        except KeyboardInterrupt:
            print("\n\n程序被用户中断！")
            print("进度已保存，下次运行时选择'继续上次任务'即可从断点继续。")
            self.save_progress()
        except Exception as e:
            print(f"\n✗ 程序运行出错: {e}")
            import traceback
            traceback.print_exc()
            print("\n进度已保存")
            self.save_progress()
        finally:
            print("\n是否关闭浏览器？(y/n): ")
            try:
                if input().strip().lower() == 'y':
                    self.cleanup()
                else:
                    print("浏览器保持打开状态，可以手动检查")
            except:
                self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("✓ 浏览器已关闭")
        except Exception as e:
            print(f"关闭浏览器时出错: {e}")


if __name__ == "__main__":
    print("="*60)
    print("中国裁判文书网自动化采集程序 (支持断点续传)")
    print("="*60)
    
    scraper = CourtDocumentScraper()
    
    # 检查是否存在进度文件
    has_progress = scraper.load_progress()
    
    if has_progress:
        print("\n检测到未完成的任务！")
        print("1. 继续上次任务")
        print("2. 开始新任务")
        choice = input("\n请选择 (1/2): ").strip()
        
        if choice == "1":
            # 继续上次任务
            keywords = scraper.progress.get('keywords', [])
            if keywords:
                max_pages_input = input(f"请输入最大翻页数 (默认5页): ").strip()
                max_pages = int(max_pages_input) if max_pages_input.isdigit() else 5
                
                print(f"\n配置信息:")
                print(f"- 关键词数量: {len(keywords)}")
                print(f"- 最大翻页数: {max_pages}")
                print(f"- 每篇间隔: 300秒")
                print(f"- 加载超时: 30秒（超时自动刷新一次）")
                print("\n按Enter键开始运行...")
                input()
                
                scraper.run(keywords[0], max_pages, resume=True)
            else:
                print("进度文件中没有关键词信息，请开始新任务")
        else:
            # 开始新任务
            scraper.reset_progress()
    
    if not has_progress or choice == "2":
        print("\n请选择输入方式:")
        print("1. 直接输入单个关键词")
        print("2. 从TXT文件导入关键词")
        
        choice = input("\n请输入选择 (1/2): ").strip()
        
        if choice == "1":
            keyword = input("请输入关键词: ").strip()
        elif choice == "2":
            keyword = input("请输入TXT文件路径: ").strip()
        else:
            print("无效选择，程序退出")
            exit()
        
        max_pages_input = input("请输入最大翻页数 (默认5页): ").strip()
        max_pages = int(max_pages_input) if max_pages_input.isdigit() else 5
        
        print(f"\n配置信息:")
        print(f"- 关键词/文件: {keyword}")
        print(f"- 最大翻页数: {max_pages}")
        print(f"- 每篇间隔: 300秒")
        print(f"- 加载超时: 30秒（超时自动刷新一次）")
        print("\n按Enter键开始运行...")
        input()
        
        scraper.run(keyword, max_pages, resume=False)