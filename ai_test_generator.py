import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv

load_dotenv()

# 為了區分是驗證錯誤還是其他錯誤，定義一個專用的驗證錯誤異常
class ValidationError(Exception):
    """驗證錯誤異常"""
    pass

class SelectorValidator:
    """通用實際選擇器驗證器 - 適用於任何網站"""
    
    def __init__(self, timeout: int = 30000, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self.browser = None
        self.page = None
        self.validation_results = []
    
    def extract_primary_selectors_from_strategy(self, strategy_data: dict) -> list:
        """從策略數據中提取主要選擇器（按順序）"""
        selectors = []
        target_elements = strategy_data.get('ai_enhanced_target_elements', [])
        
        for i, element in enumerate(target_elements):
            selector_strategy = element.get('selector_strategy', {})
            primary = selector_strategy.get('primary', '')
            
            if primary:
                selectors.append({
                    'selector': primary,
                    'element_index': i,
                    'element_type': element.get('element_type', ''),
                    'purpose': element.get('purpose', ''),
                    'element_action': element.get('action', ''),
                    'reasoning': selector_strategy.get('reasoning', '')
                })
        
        return selectors
    
    def validate_selectors_sequentially(self, target_website: str, selectors: list) -> dict:
        """按順序驗證選擇器，自然跟隨用戶流程"""
        
        try:
            with sync_playwright() as p:
                self.browser = p.chromium.launch(headless=self.headless)
                self.page = self.browser.new_page()
                self.page.set_default_timeout(self.timeout)
                
                # 執行順序驗證
                results = self._execute_sequential_validation(target_website, selectors)
                
                return results
                
        except Exception as e:
            raise ValidationError(f"瀏覽器啟動失敗: {str(e)}")
    
    def _execute_sequential_validation(self, target_website: str, selectors: list) -> dict:
        """執行順序驗證"""
        validation_results = []
        
        try:
            # 載入初始頁面
            print(f"\n🏠 載入初始頁面")
            self._load_page(target_website, '初始頁面')
            
            # 按順序測試每個選擇器
            for i, selector_info in enumerate(selectors, 1):
                print(f"\n📍 選擇器 {i}/{len(selectors)}")
                
                # 測試選擇器
                result = self._test_single_selector(selector_info)
                validation_results.append(result)
                
                # 嘗試進行導航
                if self._should_attempt_navigation(result, selector_info):
                    self._attempt_navigation(selector_info)
            
            # 計算驗證結果
            return self._calculate_validation_results(validation_results)
            
        except ValidationError:
            # 重新拋出驗證錯誤
            raise
        except Exception as e:
            raise ValidationError(f"順序驗證執行失敗: {str(e)}")
    
    def _load_page(self, url: str, page_name: str):
        """載入頁面並檢查是否成功"""
        try:
            print(f"   🔄 正在載入 {page_name}: {url}")
            response = self.page.goto(url)
            
            if not response or response.status >= 400:
                raise ValidationError(f"{page_name}載入失敗 - HTTP {response.status if response else 'No Response'}")
            
            # 等待頁面載入完成
            self.page.wait_for_load_state('networkidle', timeout=self.timeout)
            print(f"   ✅ {page_name}載入成功")
            
        except Exception as e:
            raise ValidationError(f"{page_name}載入失敗: {str(e)}")
    
    def _test_single_selector(self, selector_info: dict) -> dict:
        """測試單個選擇器"""

        VALID_ACTIONS = {'click', 'hover', 'type', 'verify', 'navigate'}

        selector = selector_info['selector']
        purpose = selector_info['purpose']
        action = selector_info.get('element_action', '').lower().strip()

        # 驗證 action 是否合法
        if action and action not in VALID_ACTIONS:
            result = {
                'selector': selector,
                'purpose': purpose,
                'element_type': selector_info['element_type'],
                'success': False,
                'error': f'不支援的動作類型: {action}，僅支援: {", ".join(VALID_ACTIONS)}',
                'current_url': self.page.url
            }
            print(f"      ❌ 不支援的動作: {action}")
            return result
        
        print(f"   🎯 測試: {purpose}")
        print(f"      選擇器: {selector}")

        
        result = {
            'selector': selector,
            'purpose': purpose,
            'element_type': selector_info['element_type'],
            'success': False,
            'element_found': False,
            'element_visible': False,
            'text_matches': None,
            'error': None,
            'current_url': self.page.url
        }
        
        try:
            # 直接使用原始選擇器，不做任何轉換
            locator = self._create_locator_from_selector(selector)
            
            # 檢查元素是否存在
            element_count = locator.count()
            if element_count == 0:
                result['error'] = '元素不存在'
                print(f"      ❌ 元素不存在")
                return result
            
            result['element_found'] = True
            print(f"      ✅ 找到 {element_count} 個元素")
            
            # 檢查第一個元素的可見性
            first_element = locator.first
            is_visible = first_element.is_visible()
            result['element_visible'] = is_visible

            
            if not is_visible:
                result['error'] = '元素不可見'
                print(f"      ❌ 元素不可見")
                return result

            print(f"      ✅ 元素可見")
            
            
            # 根據 action 進行實際可行性測試
            action = selector_info.get('element_action', '').lower().strip()

            if action == 'click':
                # 測試點擊可行性
                try:
                    is_enabled = first_element.is_enabled()
                    if not is_enabled:
                        result['error'] = '元素不可點擊'
                        print(f"      ❌ 元素不可點擊")
                        return result
                    
                    # 檢查元素是否真的可以接收點擊
                    bounding_box = first_element.bounding_box()
                    if not bounding_box or bounding_box['width'] == 0 or bounding_box['height'] == 0:
                        result['error'] = '元素沒有可點擊的區域'
                        print(f"      ❌ 元素沒有可點擊的區域")
                        return result
                        
                    print(f"      ✅ 元素可以點擊")
                    
                except Exception as e:
                    result['error'] = f'點擊測試失敗: {str(e)}'
                    print(f"      ❌ 點擊測試異常: {e}")
                    return result

            elif action == 'type':
                # 測試輸入可行性
                try:
                    # 嘗試 focus 操作
                    first_element.focus()
                    
                    # 檢查是否可編輯
                    is_editable = first_element.is_editable()
                    if not is_editable:
                        result['error'] = '元素不可編輯'
                        print(f"      ❌ 元素不可編輯")
                        return result
                    
                    # 嘗試清空並輸入測試文字（不影響頁面狀態）
                    try:
                        original_value = first_element.input_value()
                    except:
                        original_value = first_element.text_content()
                    
                    # 嘗試輸入測試
                    first_element.clear()
                    first_element.fill("test")
                    
                    # 檢查是否真的可以輸入
                    current_value = ""
                    try:
                        current_value = first_element.input_value()
                    except:
                        current_value = first_element.text_content()
                    
                    if "test" not in current_value:
                        result['error'] = '元素無法接受輸入'
                        print(f"      ❌ 元素無法接受輸入")
                        return result
                    
                    # 恢復原始值
                    first_element.clear()
                    if original_value:
                        first_element.fill(original_value)
                    
                    print(f"      ✅ 元素可以輸入")
                    
                except Exception as e:
                    result['error'] = f'輸入測試失敗: {str(e)}'
                    print(f"      ❌ 輸入測試異常: {e}")
                    return result

            elif action == 'hover':
                # 測試懸停可行性
                try:
                    # 嘗試懸停操作
                    first_element.hover()
                    
                    # 懸停通常都會成功，除非元素有問題
                    print(f"      ✅ 元素可以懸停")
                    
                except Exception as e:
                    result['error'] = f'懸停測試失敗: {str(e)}'
                    print(f"      ❌ 懸停測試異常: {e}")
                    return result

            elif action == 'verify':
                # 測試驗證可行性
                try:
                    # 檢查元素是否有可驗證的內容
                    has_text = bool(first_element.text_content())
                    has_value = False
                    has_attribute = False
                    
                    try:
                        has_value = bool(first_element.input_value())
                    except:
                        pass
                    
                    try:
                        # 檢查一些常見的可驗證屬性
                        common_attrs = ['title', 'alt', 'data-value', 'aria-label']
                        for attr in common_attrs:
                            if first_element.get_attribute(attr):
                                has_attribute = True
                                break
                    except:
                        pass
                    
                    if not (has_text or has_value or has_attribute):
                        result['error'] = '元素沒有可驗證的內容'
                        print(f"      ⚠️ 警告: 元素沒有明顯可驗證的內容")
                        # 不直接失敗，因為可能有其他驗證方式
                    
                    print(f"      ✅ 元素可以進行驗證")
                    
                except Exception as e:
                    result['error'] = f'驗證測試失敗: {str(e)}'
                    print(f"      ❌ 驗證測試異常: {e}")
                    return result

            elif action == 'navigate':
                # 測試導航可行性
                try:
                    # 檢查是否有導航相關的屬性
                    href = first_element.get_attribute("href")
                    onclick = first_element.get_attribute("onclick")
                    cursor = first_element.evaluate("el => getComputedStyle(el).cursor")
                    
                    # 檢查是否有導航的跡象
                    has_navigation_signs = (
                        href and href != "#" and not href.startswith("javascript:void") or
                        onclick or
                        cursor == "pointer"
                    )
                    
                    if not has_navigation_signs:
                        result['error'] = '元素沒有導航功能的跡象'
                        print(f"      ⚠️ 警告: 元素沒有明顯的導航功能跡象")
                        # 不直接失敗，因為可能有其他導航方式
                    
                    print(f"      ✅ 元素可能支援導航")
                    
                except Exception as e:
                    result['error'] = f'導航測試失敗: {str(e)}'
                    print(f"      ❌ 導航測試異常: {e}")
                    return result

            else:
                # 未知 action（應該在前面的 VALID_ACTIONS 檢查中被攔截）
                result['error'] = f'未知的動作類型: {action}'
                print(f"      ❌ 未知動作: {action}")
                return result
                
            # 檢查文本內容（如果選擇器包含文本期望）
            text_expectation = self._extract_text_expectation(selector)
            if text_expectation:
                actual_text = first_element.text_content() or ''
                text_matches = text_expectation in actual_text
                result['text_matches'] = text_matches
                
                if not text_matches:
                    result['error'] = f'文本不匹配，期望包含: {text_expectation}, 實際: {actual_text[:50]}'
                    print(f"      ❌ 文本不匹配")
                    return result
                
                print(f"      ✅ 文本匹配")
            
            # 所有檢查都通過
            result['success'] = True
            print(f"      🎉 選擇器驗證成功")
            
        except Exception as e:
            # 檢查是否是不兼容的語法
            if ':contains(' in selector:
                result['error'] = 'Playwright 不支援 :contains() 偽選擇器語法'
            else:
                result['error'] = str(e)
            print(f"      ❌ 驗證失敗: {result['error']}")
        
        return result
    
    

    def _create_locator_from_selector(self, selector: str):
        """創建 Playwright Locator，不做任何轉換"""

        # 處理特殊的非選擇器情況
        if selector.startswith('N/A') or 'window.location' in selector:
            raise ValidationError(f'無效的選擇器語法: {selector}')
        
        # 檢查不兼容的語法並直接拋錯
        if ':contains(' in selector:
            raise ValidationError('Playwright 不支援 :contains() 偽選擇器語法')
        
        # 處理 XPath
        if selector.startswith('//'):
            return self.page.locator(f"xpath={selector}")
        
        # 處理 CSS 選擇器
        return self.page.locator(selector)
    
    def _extract_text_expectation(self, selector: str) -> str:
        """從選擇器中提取文本期望（用於驗證）"""
        # 從 XPath text() 中提取
        text_match = re.search(r"text\(\)='([^']+)'", selector)
        if text_match:
            return text_match.group(1)
        
        # 從 normalize-space() 中提取
        normalize_match = re.search(r"normalize-space\(\)='([^']+)'", selector)
        if normalize_match:
            return normalize_match.group(1)
        
        # 從 contains(text(), ...) 中提取
        contains_text_match = re.search(r"contains\(text\(\),\s*['\"]([^'\"]+)['\"]", selector)
        if contains_text_match:
            return contains_text_match.group(1)
        
        return None
    
    def _should_attempt_navigation(self, result: dict, selector_info: dict) -> bool:
        """判斷是否應該嘗試導航"""
        if not result['success']:
            return False
        
        action = selector_info.get('element_action', '').lower().strip()
        element_type = selector_info.get('element_type', '').lower()
        
        # 基於 action 和 element_type 判斷
        is_navigation_action = action in ['click', 'navigate']
        is_navigation_element = any(keyword in element_type for keyword in 
                                ['link', 'button', 'menu', 'nav'])
        
        return is_navigation_action and is_navigation_element
    

    def _attempt_navigation(self, selector_info: dict):
        """嘗試點擊鏈接進行導航"""
        try:
            print(f"   🔄 嘗試點擊導航: {selector_info['purpose']}")
            
            # 記錄當前 URL
            original_url = self.page.url
            
            # 創建定位器並點擊
            locator = self._create_locator_from_selector(selector_info['selector'])
            
            # 點擊第一個元素
            locator.first.click()
            
            # 等待可能的導航
            try:
                self.page.wait_for_load_state('networkidle', timeout=10000)  
            except:
                pass  # 如果沒有導航也沒關係
            
            # 檢查是否發生了導航
            new_url = self.page.url
            if new_url != original_url:
                print(f"   ✅ 導航成功: {original_url} → {new_url}")
            else:
                print(f"   ℹ️ 點擊完成，頁面未改變")
                
        except Exception as e:
            # 導航失敗不算致命錯誤，只記錄日誌
            print(f"   ⚠️ 導航嘗試失敗: {e}")
    
    def _calculate_validation_results(self, validation_results: list) -> dict:
        """計算驗證結果"""
        total_selectors = len(validation_results)
        successful_selectors = sum(1 for r in validation_results if r['success'])
        failed_selectors = total_selectors - successful_selectors
        
        if total_selectors == 0:
            failure_rate = 0
        else:
            failure_rate = (failed_selectors / total_selectors) * 100
        
        # 收集失敗詳情
        failed_details = [r for r in validation_results if not r['success']]
        
        print(f"\n📊 驗證結果統計:")
        print(f"   總選擇器: {total_selectors}")
        print(f"   成功: {successful_selectors} ✅")
        print(f"   失敗: {failed_selectors} ❌")
        print(f"   失敗率: {failure_rate:.1f}%")
        
        return {
            'total_selectors': total_selectors,
            'successful_selectors': successful_selectors,
            'failed_selectors': failed_selectors,
            'failure_rate': failure_rate,
            'failed_details': failed_details,
            'all_results': validation_results,
            'validation_passed': failure_rate  <= 0  
        }

class StrategyValidator:
    """通用策略驗證器"""
    
    def __init__(self):
        self.selector_validator = SelectorValidator()
    
    def validate_strategy(self, test_strategy: str, target_website: str) -> dict:
        """
        驗證策略文件 - 使用通用實際瀏覽器測試
        
        Args:
            test_strategy: JSON 格式的測試策略
            target_website: 目標網站 URL
        
        Returns:
            驗證結果字典
        
        Raises:
            ValidationError: 當驗證失敗時拋出
        """
        try:
            strategy_data = json.loads(test_strategy)
        except json.JSONDecodeError as e:
            raise ValidationError(f"策略格式錯誤: {e}")
        
        print("🔍 開始選擇器驗證...")
        
        # 提取主要選擇器
        selectors = self.selector_validator.extract_primary_selectors_from_strategy(strategy_data)
        
        if not selectors:
            return {
                'validation_passed': True,
                'message': '未發現需要驗證的主要選擇器'
            }
        
        print(f"📋 將按順序驗證 {len(selectors)} 個主要選擇器")
        
        # 執行實際驗證
        results = self.selector_validator.validate_selectors_sequentially(target_website, selectors)
        
        # 檢查是否通過驗證
        if not results['validation_passed']:
            # 準備失敗報告
            failed_details = []
            for failure in results['failed_details'][:3]:  # 只顯示前3個失敗
                failed_details.append(f"• {failure['purpose']}: {failure['error']}")
            
            raise ValidationError(
                f"選擇器驗證失敗 - 失敗率 {results['failure_rate']:.1f}% \n"
                f"失敗的選擇器:\n" + "\n".join(failed_details)
            )
        
        # 驗證通過
        print(f"\n✅ 通用實際驗證通過!")
        print(f"   成功率: {100 - results['failure_rate']:.1f}%")
        
        return {
            'validation_passed': True,
            'validation_results': results
        }

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

重要提醒：
- 不要使用 :contains() 偽選擇器（Playwright 不支援）
- 使用標準的 CSS 選擇器或 XPath
- 如需文本匹配，使用 XPath 的 text() 或 contains() 函數


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
        self.strategy_validator = StrategyValidator()
        
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

        ⚠️ **Action 嚴格規範**：
        element_action 必須且只能使用以下值之一：
        - "click" - 點擊操作（按鈕、連結等）
        - "hover" - 懸停操作（下拉菜單觸發等）
        - "type" - 輸入操作（文字輸入框等）
        - "verify" - 驗證操作（檢查元素存在、內容等）
        - "navigate" - 導航操作（頁面跳轉）

        請嚴格使用上述英文小寫值，不要創造其他動作名稱。

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
                    "action": "操作類型（click/hover/type/verify/navigate）",
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
    
    def validate_strategy_before_generation(self, test_strategy: str) -> bool:
        """
        在生成測試代碼前驗證策略
        如果驗證失敗會拋出 ValidationError 異常
        """
        
        try:
            validation_result = self.strategy_validator.validate_strategy(
                test_strategy, 
                self.target_website
            )
            
            return True
            
        except ValidationError as e:
            print(f"\n❌ 驗證失敗:")
            print(f"   {str(e)}")
            print(f"\n🛑 測試生成已停止，請修正上述問題後重試")
            return False
        except Exception as e:
            print(f"\n⚠️ 驗證過程發生錯誤: {e}")
            print(f"⚠️ 繼續生成測試代碼，但建議檢查選擇器")
            return True
    

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
                
            def test_scenario_1(self):
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
        - 測試方法直接使用 self.page_object（不要添加參數）
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
        print("\n🔍 步驟 1/5: AI 驅動網站分析")
        analysis_result = self.ai_driven_website_analysis(test_requirements)
        
        # 步驟 2: 生成 AI 驅動測試策略
        print("\n🧠 步驟 2/5: 生成 AI 驅動測試策略")
        test_cases = self.generate_ai_driven_test_case(analysis_result, test_requirements)

        # 步驟 3: 策略驗證 (新增的驗證步驟)
        print("\n🛡️ 步驟 3/5: 策略驗證 (鏈接 + 選擇器)")
        print("=" * 50)
        validation_passed = self.validate_strategy_before_generation(test_cases)
        
        if not validation_passed:
            return {
                "success": False,
                "error": "策略驗證失敗，測試生成已停止",
                "test_requirements": test_requirements,
                "target_website": self.target_website,
                "timestamp": datetime.now().isoformat(),
                "suggestion": "請檢查並修正策略中的鏈接和選擇器問題後重試"
            }
        
        # 步驟 3: 生成 AI 驅動測試代碼 (只有驗證通過才會執行)
        print("\n⚡ 步驟 4/5: 生成 AI 驅動測試代碼")
        test_code = self.generate_ai_driven_test_code(analysis_result, test_cases, test_requirements)
        
        # 步驟 4: 保存所有文件
        print("\n💾 步驟 5/5: 保存生成的文件")
        saved_files = self.save_generated_files(analysis_result, test_cases, test_code, test_requirements)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = {
            "success": True,
            "test_requirements": test_requirements,
            "target_website": self.target_website,
            "generation_time": duration,
            "validation_passed": True,
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
        print(f"🛡️ 驗證結果: {'✅ 通過' if result.get('validation_passed') else '❌ 失敗'}")
        
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