import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

load_dotenv()

class AIElementAnalyzer:
    """AI 驅動的元素分析器 - 讓 AI 自主發現和分析網站元素"""
    
    def __init__(self, page: Page, model):
        self.page = page
        self.model = model
        
    def capture_page_snapshot(self) -> Dict[str, Any]:
        """捕獲頁面快照信息，供 AI 分析"""
        print("📸 捕獲頁面快照...")
        
        snapshot = {
        "url": self.page.url,
        "title": self.page.title(),
        "page_content": self.page.content() #self._get_essential_html(),  # 只保留關鍵 HTML
    }
        return snapshot
    
    # def _get_essential_html(self) -> str:
    #     """獲取去除雜訊的核心 HTML"""
    #     try:
    #         # 移除所有 style、comment，保留結構和內容
    #         cleaned_html = self.page.evaluate("""
    #         () => {
    #             const clone = document.documentElement.cloneNode(true);
                
    #             // 移除雜訊元素
    #             const noise = clone.querySelectorAll('style, meta, link');
    #             noise.forEach(el => el.remove());
                
    #             // 簡化屬性，只保留重要的
    #             const elements = clone.querySelectorAll('*');
    #             elements.forEach(el => {
    #                 // 保留重要屬性
    #                 const keepAttrs = ['id', 'class', 'type', 'name', 'href', 'placeholder', 'value'];
    #                 const attrs = Array.from(el.attributes);
    #                 attrs.forEach(attr => {
    #                     if (!keepAttrs.includes(attr.name)) {
    #                         el.removeAttribute(attr.name);
    #                     }
    #                 });
    #             });
                
    #             return clone.outerHTML;
    #         }
    #         """)
            
    #         return cleaned_html if cleaned_html else ""
            
    #     except Exception as e:
    #         print(f"HTML 清理失敗: {e}")
    #         return self.page.content()[:50000]
    
    def ai_analyze_page_functionality(self, snapshot: Dict[str, Any], test_requirements:str) -> Dict[str, Any]:
        """讓 AI 自主分析頁面功能和元素"""
        prompt = f"""
作為專業的網頁自動化測試專家，請基於以下**實際網站快照數據**進行精確分析。

🎯 **重要指導原則**：
1. **僅基於提供的實際數據** - 不要假設任何未在快照中發現的元素
2. **使用實際元素文字** - 基於 actual_element_samples 中的真實文字內容
3. **選擇器必須實用** - 基於真實DOM結構，避免過度假設
4. **驗證邏輯要可執行** - 確保JavaScript檢查邏輯在實際瀏覽器中可運行

📊 **網站實際快照數據**：

🌐 **基本信息**：
- URL: {snapshot['url']}
- 頁面標題: {snapshot['title']}

📋 作為網頁測試專家，請分析以下**完整的網頁內容**（包含功能相關的 JavaScript）：
    ```html
    {snapshot.get('page_content', '')} 
    ```
🎯 **分析要求**：
    1. **從 HTML 中發現** - 基於實際存在的元素，不要假設
    2. **語言無關** - 適用任何語言的網站
    3. **框架無關** - 不假設任何 CSS 框架或命名慣例
    4. **生成通用選擇器** - 基於實際的標籤、屬性、文字內容    
    5. **JavaScript 中的功能定義** - 許多現代網站把功能邏輯放在 JS 中

    使用者的需求: {test_requirements}

💡 **具體分析使用者的要求**：

    1. **功能發現**：基於實際元素和關鍵字，推斷網站的核心功能
    2. **選擇器設計**：使用實際發現的元素文字和屬性來設計選擇器
    3. **測試場景**：基於真實的元素互動設計可執行的測試場景
    4. **驗證邏輯**：編寫在實際瀏覽器環境中可運行的JavaScript檢查


🎯 **期望的JSON回應格式**：

{{
  "discovered_functionality": [
    "基於實際快照數據發現的功能1：具體描述為什麼認為存在此功能",
    "功能2：引用具體的元素證據和關鍵字證據"
  ],
  "recommended_test_approach": "基於實際發現元素的測試策略，說明測試重點和方法",
  "ai_generated_selectors": {{
    "primary_interaction_elements": [
      {{
        "element_purpose": "基於實際元素分析的用途",
        "recommended_selector": "基於實際元素文字/屬性的最佳選擇器",
        "fallback_selectors": [
          "備選方案1 - 基於實際DOM結構",
          "備選方案2 - 使用更通用的選擇器"
        ],
        "selection_reasoning": "選擇此選擇器的具體原因，引用實際發現的元素證據",
        "real_element_evidence": "引用actual_element_samples中的具體證據"
      }}
    ],
    "content_verification_targets": [
      {{
        "verification_purpose": "驗證目的",
        "content_selector": "內容選擇器",
        "expected_patterns": ["基於實際內容的期望模式"],
        "validation_method": "具體的驗證方法"
      }}
    ]
  }},
  "ai_validation_logic": {{
    "success_indicators": [
      {{
        "condition_name": "成功條件名稱",
        "javascript_check": "可在瀏覽器console執行的JavaScript代碼",
        "reasoning": "為什麼這個條件表示成功",
        "evidence_source": "基於快照中的哪些證據"
      }}
    ],
    "failure_indicators": [
      {{
        "condition_name": "失敗條件名稱",
        "javascript_check": "可執行的JavaScript檢查代碼", 
        "reasoning": "為什麼這個條件表示失敗"
      }}
    ]
  }},
  "ai_test_scenarios": [
    {{
      "scenario_name": "基於實際元素設計的測試場景名稱",
      "scenario_description": "場景描述，說明測試什麼功能",
      "interaction_steps": [
        {{
          "action": "具體操作類型（navigate/click/type/select等）",
          "target": "操作目標（URL或選擇器）",
          "value": "操作值（如果需要）",
          "reasoning": "為什麼執行這個操作"
        }}
      ],
      "validation_strategy": "如何驗證測試結果，引用上面定義的validation_logic"
    }}
  ]
}}

⚠️ **特別注意**：
- 所有選擇器必須基於實際發現的元素
- JavaScript檢查邏輯必須可以在瀏覽器console中執行
- 測試場景必須基於真實存在的互動元素
- 不要編造不存在的功能或元素

請基於以上實際數據進行精確分析，返回詳細的JSON格式結果。
"""
        
        try:
            response = self.model.generate_content(prompt)
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                ai_analysis = json.loads(json_match.group())
                print("✅ 增強版AI分析完成")
                return ai_analysis
            else:
                print("❌ AI分析格式錯誤，使用備用分析")
               
                
        except Exception as e:
            print(f"❌ AI分析失敗: {e}")
            

class AutomatedTestGenerator:
    """AI 驅動的完全自動化測試生成器"""
    
    def __init__(self, api_key: str, target_website: str = "https://shop.findarts.net"):
        self.api_key = api_key
        self.target_website = target_website
        self.setup_gemini()
        self.output_dir = Path("auto_generated_tests")
        self.output_dir.mkdir(exist_ok=True)
        
    def setup_gemini(self):
        """設置 Gemini AI"""
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro-preview-05-06')
    
    def ai_driven_website_analysis(self,test_requirements) -> Dict[str, Any]:
        """AI 驅動的網站分析"""
        print("🔍 開始 AI 驅動的網站分析...")
        
        analysis_result = {
            "url": self.target_website,
            "page_snapshot": {},
            "ai_analysis": {},
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()
                
                print(f"📱 載入網站: {self.target_website}")
                page.goto(self.target_website, wait_until='networkidle')
                
                # 使用 AI 元素分析器
                ai_analyzer = AIElementAnalyzer(page, self.model)
                
                # 捕獲頁面快照
                snapshot = ai_analyzer.capture_page_snapshot()
                analysis_result["page_snapshot"] = snapshot
                
                # AI 自主分析
                ai_analysis = ai_analyzer.ai_analyze_page_functionality(snapshot,test_requirements)
                analysis_result["ai_analysis"] = ai_analysis

                browser.close()
                
        except Exception as e:
            print(f"❌ AI 驅動分析失敗: {e}")
            
        return analysis_result
    
    def generate_ai_driven_test_case(self, analysis_result: Dict[str, Any], test_requirements: str) -> str:
        """基於 AI 分析生成測試場景和策略"""
        print("🧠 生成 AI 驅動的測試策略...")
        
        prompt = f"""
        基於 AI 自主分析結果，生成完整的測試實施策略。

        🎯 **用戶測試需求**: {test_requirements}

        📊 **AI 自主分析結果**:
        {json.dumps(analysis_result.get('ai_analysis', {}), ensure_ascii=False, indent=2)}

        📸 **頁面快照摘要**:
        - URL: {analysis_result.get('page_snapshot', {}).get('url', '')}
        - 標題: {analysis_result.get('page_snapshot', {}).get('title', '')}

        🚀 **請將 AI 分析轉化為具體的測試實施策略**:

        1. **整合用戶需求與 AI 發現** - 結合用戶要求和 AI 自主發現的功能
        2. **優化 AI 生成的選擇器** - 基於實際可行性調整 AI 推薦的選擇器
        3. **完善驗證邏輯** - 將 AI 的驗證邏輯轉化為具體的實施代碼
        4. **設計測試流程** - 基於 AI 場景設計具體的測試步驟
        5. 請根據 AI 分析結果，生成一個正確的validation_methods

        ⚠️ **JavaScript 驗證邏輯要求 - 確保語法正確**：
        - 所有 JavaScript 代碼必須是簡單的布林表達式
        - 不要使用變數聲明、return 語句或複雜邏輯
        - 使用正確的引號轉義：`document.querySelector('input[type="search"]') !== null`
        - 避免複雜的邏輯組合

        請返回 JSON 格式的實施策略:

        {{
            "implementation_strategy": "基於AI分析和用戶需求的實施策略描述",
            "timeout_settings": {{
                "default_timeout": 30000,
                "navigation_timeout": 30000,
                "element_wait_timeout": 30000
            }},
            "ai_enhanced_target_elements": [
                {{
                    "element_type": "基於AI分析的元素類型",
                    "selector_strategy": {{
                        "primary": "AI推薦的主要選擇器",
                        "fallbacks": ["AI推薦的備選選擇器"],
                        "reasoning": "選擇器選用原因"
                    }},
                    "action": "操作類型",
                    "purpose": "AI分析的元素用途"
                }}
            ],
            "ai_generated_test_scenarios": [
                {{
                    "scenario_name": "基於AI分析的測試場景",
                    "steps": ["具體實施步驟"],
                    "expected_result": "基於AI驗證邏輯的期望結果",
                    "validation_approach": "驗證方法"
                }}
            ],
            "validation_methods": {{
                "dynamic_success_checks": [
                    {{
                        "check_name": "檢查名稱",
                        "javascript_logic": "根據分析結果的JavaScript檢查邏輯",
                        "description": "檢查描述"
                    }}
                ],
                "dynamic_failure_checks": [
                    {{
                        "check_name": "檢查名稱", 
                        "javascript_logic": "根據分析結果的JavaScript檢查邏輯",
                        "description": "檢查描述"
                    }}
                ]
            }}
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                return json_match.group()
            else:
                return response.text
        except Exception as e:
            print(f"❌ 策略生成失敗: {e}")
            return "{}"
    
    def generate_ai_driven_test_code(self, analysis_result: Dict[str, Any], test_strategy: str, test_requirements: str) -> str:
        """生成基於 AI 分析的測試代碼"""
        print("⚡ 生成 AI 驅動的測試代碼...")
        
        prompt = f"""
        基於完整的 AI 分析結果和實施策略，生成高質量的 Playwright Python 測試代碼。
        並基於test_scenarios生成具體的測試方法。
        
        🎯 **測試需求**: {test_requirements}

        📊 **AI 分析結果**:
        {json.dumps(analysis_result, ensure_ascii=False, indent=2)}

        🧠 **實施策略**:
        {test_strategy}

        ⚡ **代碼生成要求**:
        1. **完全基於 AI 分析** - 使用 AI 推薦的選擇器和驗證邏輯
        2. **動態元素查找** - 實現基於 AI 分析的智能元素定位
        3. **AI 驗證邏輯** - 整合 AI 生成的 JavaScript 檢查邏輯
        4. **容錯機制** - 基於 AI 推薦的備選方案實現容錯
        5. **詳細註解** - 說明每個決策的 AI 分析依據

        ⚠️ **Fixture 錯誤修正要求**:
       
        **標準 Playwright Pytest 結構**:
        ```python
        import pytest
        from playwright.sync_api import Page, Browser, BrowserContext, sync_playwright

        # ✅ 正確的 fixture 定義方式
        @pytest.fixture(scope="session")
        def browser():
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)  # 設定 headless=False 方便除錯
                yield browser
                browser.close()

        @pytest.fixture(scope="function") 
        def page(browser):
            context = browser.new_context(
                viewport={{'width': 1280, 'height': 720}},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            yield page
            context.close()

        ```
        

        ⚠️ **關鍵語法要求 - 必須嚴格遵守**:

        1. **使用同步 API - 絕對不要使用 await**:
        - ✅ 正確: element.click()
        - ✅ 正確: page.goto(url)
        - ✅ 正確: page.wait_for_load_state('networkidle')
        - ❌ 錯誤: await element.click()
        - ❌ 錯誤: await page.goto(url)

        2. **Playwright 同步選擇器語法**:
        - ✅ 正確: page.get_by_text("加入購物車").click()
        - ✅ 正確: page.locator("button[type='submit']").click()
        - ✅ 正確: page.locator("input[name='search']").fill("關鍵字")
        - ❌ 錯誤: page.locator("button")("加入購物車") # locator 不是函數
        - ❌ 錯誤: await page.locator("button").click()

        3. **函數定義**:
        - ✅ 正確: def test_function(self, page_object):
        - ❌ 錯誤: async def test_function(self, page_object):

        4. **等待機制**:
        - ✅ 正確: time.sleep(3)
        - ✅ 正確: page.wait_for_load_state('networkidle')
        - ✅ 正確: page.wait_for_timeout(2000)
        - ❌ 錯誤: await page.wait_for_load_state('networkidle')

        5. **元素操作**:
        - ✅ 正確: element = page.locator("selector"); element.click()
        - ✅ 正確: page.locator("selector").click()
        - ❌ 錯誤: page.locator("selector")("text") # 不能這樣調用

        6. **條件檢查**:
        - ✅ 正確: if page.locator("selector").is_visible():
        - ✅ 正確: element.wait_for(state="visible")
        - ❌ 錯誤: await element.wait_for(state="visible")

        🏗️ **測試代碼結構要求**:

        ```python
        import pytest
        import time
        from playwright.sync_api import Page, expect
        
        class FilterTestPageObject:
            def __init__(self, page: Page):
                self.page = page
                
            def navigate_to_website(self):
                # 使用同步API，不要用await
                self.page.goto("URL")
                self.page.wait_for_load_state('networkidle')
                
            def find_element_intelligently(self, primary_selector, fallback_selectors):
                # 智能元素查找，基於AI推薦的選擇器
                try:
                    element = self.page.locator(primary_selector)
                    if element.count() > 0:
                        return element
                except:
                    pass
                    
                for fallback in fallback_selectors:
                    try:
                        element = self.page.locator(fallback)
                        if element.count() > 0:
                            return element
                    except:
                        continue
                return None
        
        class TestAIGeneratedFilters:
            @pytest.fixture(autouse=True)
            def setup(self, page: Page):
                self.page_object = FilterTestPageObject(page)
                page.set_default_timeout(30000)
                
            def test_scenario_1(self, page_object):
                # 測試方法實現
                pass
        ```

        請生成完整的 pytest 測試檔案，包含：
        
        1. 所有必要的 import 語句
        2. 完整的 Page Object Model 類別  
        3. 至少 5 個具體的測試方法
        4. 基於 AI 分析的智能選擇器查找
        5. 適當的等待機制和錯誤處理
        6. 詳細的中文註解
        7. AI 驅動的驗證邏輯
        
        測試應該包含：
        - 基於 AI 發現功能的測試
        - AI 推薦的元素互動測試
        - AI 生成的驗證邏輯測試
        
        請確保：
        - 使用 AI 分析的實際選擇器
        - 包含智能的元素查找邏輯
        - 測試穩健且容錯性強
        - 程式碼結構清晰且易於維護
        - **絕對不要使用 await 關鍵字**
        - **正確使用 Playwright 同步 API**

        重要注意事項：
        - 避免 'locator' object is not callable 錯誤
        - 測試方法參數使用 page_object
        - 所有 page 操作都通過 page_object.page 進行
        - 使用 pytest.skip() 而不是 assert False
        - 每個測試都要設定 30 秒超時
        - 所有元素檢測都要用 try-except 包裝
        
        請直接回傳完整的 Python 代碼，使用 ```python 和 ``` 包圍。
        """
        
        try:
            response = self.model.generate_content(prompt)
            code_match = re.search(r'```python\n(.*?)\n```', response.text, re.DOTALL)
            if code_match:
                return code_match.group(1)

        except Exception as e:
            print(f"❌ AI 代碼生成失敗: {e}")
            
    
    def generate_complete_test_suite(self, test_requirements: str) -> Dict[str, Any]:
        """完整的 AI 驅動測試生成流程"""
        print("🚀 開始 AI 驅動的完全自動化測試生成")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # 步驟 1: AI 驅動網站分析
        print("\n🔍 步驟 1/4: AI 驅動網站分析")
        analysis_result = self.ai_driven_website_analysis(test_requirements)
        
        # 步驟 2: 生成 AI 驅動測試策略
        print("\n🧠 步驟 2/4: 生成 AI 驅動測試策略")
        test_cases = self.generate_ai_driven_test_case(analysis_result, test_requirements)
        
        # 步驟 3: 生成 AI 驅動測試代碼
        print("\n⚡ 步驟 3/4: 生成 AI 驅動測試代碼")
        test_code = self.generate_ai_driven_test_code(analysis_result, test_cases, test_requirements)
        
        # 步驟 4: 保存所有文件
        print("\n💾 步驟 4/4: 保存生成的文件")
        saved_files = self.save_generated_files(analysis_result, test_cases, test_code, test_requirements)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = {
            "success": True,
            "test_requirements": test_requirements,
            "target_website": self.target_website,
            "generation_time": duration,
            "ai_analysis_summary": {
                "discovered_functionality": analysis_result.get('ai_analysis', {}).get('discovered_functionality', []),
                "ai_generated_scenarios": len(analysis_result.get('ai_analysis', {}).get('ai_test_scenarios', [])),
                "ai_validation_checks": len(analysis_result.get('ai_analysis', {}).get('ai_validation_logic', {}).get('success_indicators', []))
            },
            "generated_files": saved_files,
            "timestamp": datetime.now().isoformat()
        }
        
        self.display_results_summary(result)
        return result
    
    def save_generated_files(self, analysis_result: Dict[str, Any], test_strategy: str, test_code: str, test_requirements: str) -> Dict[str, str]:
        """保存生成的文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存 AI 分析結果
        analysis_file = self.output_dir / f"ai_analysis_{timestamp}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        # 保存測試策略
        strategy_file = self.output_dir / f"ai_strategy_{timestamp}.json"
        with open(strategy_file, 'w', encoding='utf-8') as f:
            f.write(test_strategy)
        
        # 保存測試代碼
        test_name = test_requirements.replace(' ', '_').replace('/', '_')
        test_file = self.output_dir / f"ai_test_{test_name}_{timestamp}.py"
        
        header = f'''"""
AI 驅動自動生成的測試檔案
測試需求: {test_requirements}
目標網站: {self.target_website}
生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

AI 自主發現的功能:
{json.dumps(analysis_result.get('ai_analysis', {}).get('discovered_functionality', []), ensure_ascii=False)}

執行方式:
1. 安裝依賴: pip install playwright pytest
2. 安裝瀏覽器: playwright install
3. 執行測試: pytest {test_file.name} -v
4. 有頭模式: pytest {test_file.name} --headed -v
"""

'''
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(header + test_code)
        
        return {
            "analysis_file": str(analysis_file),
            "strategy_file": str(strategy_file),
            "test_file": str(test_file)
        }
    
    def display_results_summary(self, result: Dict[str, Any]):
        """顯示結果摘要"""
        print("\n" + "=" * 60)
        print("📊 AI 驅動自動化測試生成結果摘要")
        print("=" * 60)
        
        print(f"🎯 測試需求: {result['test_requirements']}")
        print(f"🌐 目標網站: {result['target_website']}")
        print(f"⏱️  總耗時: {result['generation_time']:.2f} 秒")
        
        ai_summary = result['ai_analysis_summary']
        print(f"\n🤖 AI 自主分析成果:")
        print(f"   🔍 發現功能: {', '.join(ai_summary['discovered_functionality'])}")
        
        files = result['generated_files']
        print(f"\n📁 生成的文件:")
        print(f"   🤖 AI 分析: {files['analysis_file']}")
        print(f"   🧠 實施策略: {files['strategy_file']}")
        print(f"   🧪 測試代碼: {files['test_file']}")
        
        print("\n💡 後續步驟:")
        print(f"   1. 查看 AI 分析: cat {files['analysis_file']}")
        print(f"   2. 執行 AI 測試: pytest {files['test_file']} -v")
        print(f"   3. 有頭模式: pytest {files['test_file']} --headed -v")


class AutomatedTestCLI:
    """AI 驅動測試生成命令行介面"""
    
    def __init__(self, api_key: str):
        self.generator = AutomatedTestGenerator(api_key)
        
    def interactive_mode(self):
        """互動模式"""
        print("\n🤖 AI 驅動完全自動化測試生成器")
        print(f"\n🌐 預設目標網站: {self.generator.target_website}")
        
        while True:
            try:
                print("-" * 40)
 
                test_requirements = input("👤 請描述您的測試需求 (例如: 測試商品篩選功能): ").strip()
                
                if test_requirements.lower() in ['quit', 'exit', '退出', 'q']:
                    print("👋 感謝使用 AI 驅動測試生成器！")
                    break
                    
                if not test_requirements:
                    print("⚠️ 請輸入測試需求")
                    continue
                
                # 確認是否要更換網站
                change_website = input(f"🌐 是否要測試其他網站？當前: {self.generator.target_website} (y/N): ").lower()
                if change_website.startswith('y'):
                    new_website = input("請輸入新的網站 URL: ").strip()
                    if new_website:
                        self.generator.target_website = new_website
                
                print(f"\n🚀 開始 AI 驅動測試生成...")
                print(f"🎯 測試需求: {test_requirements}")
                print(f"🌐 目標網站: {self.generator.target_website}")
                print("🤖 AI 將自主分析並生成所有測試邏輯...")
                
                # 執行 AI 驅動的完整流程
                result = self.generator.generate_complete_test_suite(test_requirements)
                
                # 詢問是否繼續
                continue_testing = input("\n🔄 是否要讓 AI 測試其他功能？ (Y/n): ").lower()
                if continue_testing.startswith('n'):
                    print("👋 感謝使用 AI 驅動測試生成器！")
                    break
                    
            except KeyboardInterrupt:
                print("\n\n👋 程式已中斷，再見！")
                break
            except Exception as e:
                print(f"\n❌ 發生錯誤: {e}")
                print("請重試或輸入 'quit' 結束\n")


def main():
    """主程式入口"""
    
    # 檢查 API 金鑰
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("❌ 請設置 GEMINI_API_KEY 環境變數")
        return
    
    # 檢查 Playwright
    try:
        import subprocess
        subprocess.run(["playwright", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Playwright 未安裝或未正確設置")
    
    # 啟動 AI 驅動 CLI
    cli = AutomatedTestCLI(api_key)
    cli.interactive_mode()

if __name__ == "__main__":
    main()