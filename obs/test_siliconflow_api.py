#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硅基流动API测试工具
用于测试GLM模型API调用的连通性和可用性
"""

import os
import sys
import json
import requests
import base64
from PIL import Image
import io
import time
from typing import List, Dict, Any, Optional

class SiliconFlowAPITester:
    def __init__(self, api_key: str = None):
        """初始化API测试器"""
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("API密钥未设置。请通过参数传入或设置环境变量 SILICONFLOW_API_KEY")
        
        self.base_url = "https://api.siliconflow.cn/v1"
        
        # 不使用代理
        self.proxies = None
        
        # 测试用的模型列表
        self.test_models = [
            "THUDM/GLM-4.1V-9B-Thinking"
        ]
        
        print(f"API测试器初始化完成")
        print(f"Base URL: {self.base_url}")
        print(f"代理设置: 无代理（直连）")
        print(f"测试模型列表: {self.test_models}")
    
    def test_api_key_validity(self) -> Dict[str, Any]:
        """测试API密钥的有效性"""
        print("\n" + "="*50)
        print("测试1: API密钥有效性验证")
        print("="*50)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # 测试获取模型列表
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                models_data = response.json()
                available_models = [model.get('id', '') for model in models_data.get('data', [])]
                
                print(f"✅ API密钥有效！")
                print(f"可用模型数量: {len(available_models)}")
                print(f"可用模型列表:")
                for i, model in enumerate(available_models[:10], 1):
                    print(f"  {i}. {model}")
                if len(available_models) > 10:
                    print(f"  ... 还有 {len(available_models) - 10} 个模型")
                
                return {
                    "success": True,
                    "available_models": available_models,
                    "total_models": len(available_models)
                }
            else:
                print(f"❌ API密钥验证失败")
                print(f"状态码: {response.status_code}")
                print(f"响应: {response.text}")
                
                return {
                    "success": False,
                    "error": f"API验证失败: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            print(f"❌ API测试失败: {str(e)}")
            return {
                "success": False,
                "error": f"API测试失败: {str(e)}"
            }
    
    def test_model_availability(self, model_name: str) -> Dict[str, Any]:
        """测试特定模型的可用性"""
        print(f"\n测试模型: {model_name}")
        print("-" * 30)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 创建简单的测试消息
        data = {
            "model": model_name,
            "messages": [
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": "这是一个测试消息，请回复'测试成功'。"
                        }
                    ]
                }
            ],
            "max_tokens": 100,
            "temperature": 0.1
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                proxies=self.proxies,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 模型 {model_name} 可用")
                print(f"回复: {result['choices'][0]['message']['content']}")
                
                return {
                    "success": True,
                    "model": model_name,
                    "response": result
                }
            else:
                print(f"❌ 模型 {model_name} 调用失败")
                print(f"状态码: {response.status_code}")
                print(f"错误: {response.text}")
                
                return {
                    "success": False,
                    "model": model_name,
                    "error": f"模型调用失败: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            print(f"❌ 模型 {model_name} 测试失败: {str(e)}")
            return {
                "success": False,
                "model": model_name,
                "error": f"模型测试失败: {str(e)}"
            }
    
    def test_all_models(self) -> Dict[str, Any]:
        """测试所有配置的模型"""
        print("\n" + "="*50)
        print("测试2: 模型可用性测试")
        print("="*50)
        
        results = {}
        available_models = []
        
        for model in self.test_models:
            result = self.test_model_availability(model)
            results[model] = result
            
            if result["success"]:
                available_models.append(model)
        
        print(f"\n📊 模型测试结果汇总:")
        print(f"总测试模型数: {len(self.test_models)}")
        print(f"可用模型数: {len(available_models)}")
        
        if available_models:
            print(f"推荐使用的模型:")
            for i, model in enumerate(available_models, 1):
                print(f"  {i}. {model}")
        
        return {
            "all_results": results,
            "available_models": available_models,
            "total_test_models": len(self.test_models),
            "available_count": len(available_models)
        }
    
    def create_test_image(self) -> str:
        """创建一个测试用的简单图片"""
        # 创建一个简单的彩色图片
        img = Image.new('RGB', (224, 224), color='red')
        
        # 转换为base64
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return img_base64
    
    def test_vision_model(self, model_name: str = "THUDM/glm-4v-9b") -> Dict[str, Any]:
        """测试视觉模型"""
        print(f"\n" + "="*50)
        print(f"测试3: 视觉模型测试 - {model_name}")
        print("="*50)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 创建测试图片
        test_image = self.create_test_image()
        
        data = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "请描述这张图片的内容和主要颜色。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{test_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 200,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                proxies=self.proxies,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 视觉模型 {model_name} 测试成功")
                print(f"图片描述: {result['choices'][0]['message']['content']}")
                
                return {
                    "success": True,
                    "model": model_name,
                    "response": result
                }
            else:
                print(f"❌ 视觉模型 {model_name} 测试失败")
                print(f"状态码: {response.status_code}")
                print(f"错误: {response.text}")
                
                return {
                    "success": False,
                    "model": model_name,
                    "error": f"视觉模型测试失败: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            print(f"❌ 视觉模型 {model_name} 测试失败: {str(e)}")
            return {
                "success": False,
                "model": model_name,
                "error": f"视觉模型测试失败: {str(e)}"
            }
    
    def run_full_test(self) -> Dict[str, Any]:
        """运行完整的API测试"""
        print("🚀 开始硅基流动API完整测试")
        print("="*60)
        
        all_results = {}
        
        # 测试1: API密钥有效性
        api_test_result = self.test_api_key_validity()
        all_results["api_key_test"] = api_test_result
        
        if not api_test_result["success"]:
            print("\n❌ API密钥测试失败，停止后续测试")
            return all_results
        
        # 测试2: 模型可用性
        models_test_result = self.test_all_models()
        all_results["models_test"] = models_test_result
        
        # 测试3: 视觉模型（如果有可用模型）
        if models_test_result["available_models"]:
            # 优先测试GLM视觉模型
            vision_models = [m for m in models_test_result["available_models"] if "glm-4v" in m.lower()]
            if vision_models:
                vision_test_result = self.test_vision_model(vision_models[0])
                all_results["vision_test"] = vision_test_result
            else:
                # 测试第一个可用模型
                vision_test_result = self.test_vision_model(models_test_result["available_models"][0])
                all_results["vision_test"] = vision_test_result
        
        # 生成测试报告
        self.generate_test_report(all_results)
        
        return all_results
    
    def generate_test_report(self, results: Dict[str, Any]):
        """生成测试报告"""
        print("\n" + "="*60)
        print("📋 硅基流动API测试报告")
        print("="*60)
        
        report_file = f"siliconflow_api_test_report_{int(time.time())}.json"
        
        # 保存详细结果到文件
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成摘要
        summary = {
            "api_key_valid": results.get("api_key_test", {}).get("success", False),
            "available_models": results.get("models_test", {}).get("available_models", []),
            "vision_test_success": results.get("vision_test", {}).get("success", False),
            "recommend_model": None
        }
        
        if summary["available_models"]:
            # 优先推荐GLM视觉模型
            glm_models = [m for m in summary["available_models"] if "glm-4v" in m.lower()]
            if glm_models:
                summary["recommend_model"] = glm_models[0]
            else:
                summary["recommend_model"] = summary["available_models"][0]
        
        print(f"\n🔍 测试结果摘要:")
        print(f"API密钥有效: {'✅' if summary['api_key_valid'] else '❌'}")
        print(f"可用模型数: {len(summary['available_models'])}")
        print(f"视觉模型测试: {'✅' if summary['vision_test_success'] else '❌'}")
        
        if summary['recommend_model']:
            print(f"推荐模型: {summary['recommend_model']}")
        
        print(f"\n📄 详细测试报告已保存到: {report_file}")
        
        return summary

def main():
    """主函数"""
    print("硅基流动GLM模型API测试工具")
    print("="*50)
    
    try:
        # 创建测试器
        tester = SiliconFlowAPITester()
        
        # 运行完整测试
        results = tester.run_full_test()
        
        print("\n✅ API测试完成！")
        
    except Exception as e:
        print(f"\n❌ API测试失败: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())