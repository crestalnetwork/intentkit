"""
信念感知执行器 - 实现早退逻辑
Belief-Aware Executor with Early Exit Logic

日期：2026-03-07
作者：Claw (OpenClaw)
"""

import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from intent_schema import EnhancedIntentSchema, BeliefConfig


class BeliefProbe:
    """信念探针包装器"""
    
    def __init__(self, probe_path: str):
        """加载信念探针
        
        Args:
            probe_path: 探针 pickle 文件路径
        """
        with open(probe_path, 'rb') as f:
            self.probe = pickle.load(f)
    
    def predict_confidence(self, activation: np.ndarray) -> float:
        """预测置信度
        
        Args:
            activation: 激活向量 (hidden_dim,)
            
        Returns:
            置信度 (0-1)
        """
        # 确保输入形状正确
        if activation.ndim == 1:
            activation = activation.reshape(1, -1)
        
        # 获取正类概率
        proba = self.probe.predict_proba(activation)[0]
        return float(proba[1])  # 返回正类概率


class BeliefAwareExecutor:
    """信念感知执行器"""
    
    def __init__(self, probes_path: str = "belief-probes-v2"):
        """初始化执行器
        
        Args:
            probes_path: 信念探针目录
        """
        self.probes: List[BeliefProbe] = []
        self._load_probes(probes_path)
    
    def _load_probes(self, probes_path: str):
        """加载 24 层信念探针"""
        base_path = Path(__file__).parent / probes_path
        
        for layer_idx in range(1, 25):
            probe_path = base_path / f"probe_layer_{layer_idx}.pkl"
            if probe_path.exists():
                self.probes.append(BeliefProbe(str(probe_path)))
            else:
                raise FileNotFoundError(f"探针文件不存在：{probe_path}")
        
        print(f"已加载 {len(self.probes)} 层信念探针")
    
    async def execute_with_early_exit(
        self,
        intent: EnhancedIntentSchema,
        get_activation_fn
    ) -> Dict[str, Any]:
        """执行意图并支持早退
        
        Args:
            intent: 意图 Schema
            get_activation_fn: 获取某层激活的函数 (layer_idx) -> np.ndarray
            
        Returns:
            执行结果字典
        """
        config = intent.belief_config
        
        # 如果不启用早退，直接运行全部层
        if not config.early_exit_enabled:
            return await self._execute_full(intent, get_activation_fn)
        
        # 早退执行
        consecutive_high = 0
        layers_used = 0
        last_confidence = 0.0
        
        for layer_idx in range(1, config.max_layers + 1):
            layers_used = layer_idx
            
            # 获取该层激活
            activation = get_activation_fn(layer_idx)
            
            # 信念探针检测
            confidence = self.probes[layer_idx - 1].predict_confidence(activation)
            last_confidence = confidence
            
            # 检查早退条件
            if confidence >= config.confidence_threshold:
                consecutive_high += 1
                
                # 检查是否满足早退条件
                if (consecutive_high >= config.min_consecutive_layers and 
                    layer_idx >= config.min_layers):
                    
                    # 早退决策
                    return {
                        "exit_type": "early_exit",
                        "layers_used": layers_used,
                        "final_confidence": confidence,
                        "consecutive_high": consecutive_high,
                        "success": True
                    }
            else:
                consecutive_high = 0
        
        # 使用全部层
        return {
            "exit_type": "full_model",
            "layers_used": layers_used,
            "final_confidence": last_confidence,
            "consecutive_high": consecutive_high,
            "success": True
        }
    
    async def _execute_full(
        self,
        intent: EnhancedIntentSchema,
        get_activation_fn
    ) -> Dict[str, Any]:
        """执行全部 24 层"""
        layers_used = 24
        last_confidence = 0.0
        
        # 获取最后一层置信度
        activation = get_activation_fn(24)
        last_confidence = self.probes[23].predict_confidence(activation)
        
        return {
            "exit_type": "full_model",
            "layers_used": layers_used,
            "final_confidence": last_confidence,
            "consecutive_high": 0,
            "success": True
        }
    
    def calculate_efficiency(self, layers_used: int) -> float:
        """计算效率得分
        
        Args:
            layers_used: 实际使用的层数
            
        Returns:
            效率得分 (0-1)
        """
        return 1 - (layers_used / 24)
    
    def generate_report(
        self,
        intent: EnhancedIntentSchema,
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成执行报告
        
        Args:
            intent: 意图 Schema
            execution_result: 执行结果
            
        Returns:
            完整报告
        """
        # 更新成功标准
        intent.success_criteria = {
            "intent_achieved": execution_result["success"],
            "belief_confidence": execution_result["final_confidence"],
            "layers_used": execution_result["layers_used"],
            "efficiency_score": None,
            "alignment_score": None
        }
        
        # 计算对齐度
        alignment = intent.calculate_alignment()
        
        # 生成报告
        report = {
            "intent_name": intent.name,
            "exit_type": execution_result["exit_type"],
            "layers_used": execution_result["layers_used"],
            "layers_saved": 24 - execution_result["layers_used"],
            "efficiency": self.calculate_efficiency(execution_result["layers_used"]),
            "confidence": execution_result["final_confidence"],
            "alignment_score": alignment,
            "success": execution_result["success"]
        }
        
        return report


# 模拟激活获取函数 (用于测试)
def mock_get_activation(layer_idx: int) -> np.ndarray:
    """模拟获取某层激活
    
    Args:
        layer_idx: 层索引 (1-24)
        
    Returns:
        随机激活向量 (2048,)
    """
    # 模拟：深层置信度更高
    base_confidence = 0.5 + (layer_idx / 24) * 0.4
    activation = np.random.randn(2048) * 0.1 + base_confidence
    return activation.astype(np.float32)


async def demo():
    """演示使用"""
    print("=== 信念感知执行器演示 ===\n")
    
    # 创建执行器
    executor = BeliefAwareExecutor()
    
    # 创建搜索意图
    intent = EnhancedIntentSchema.create_search_intent()
    print(f"\n意图：{intent.name}")
    print(f"置信度阈值：{intent.belief_config.confidence_threshold}")
    print(f"最小连续层：{intent.belief_config.min_consecutive_layers}")
    print()
    
    # 执行 (使用模拟激活)
    result = await executor.execute_with_early_exit(intent, mock_get_activation)
    
    # 生成报告
    report = executor.generate_report(intent, result)
    
    print("=== 执行报告 ===")
    print(f"退出类型：{report['exit_type']}")
    print(f"使用层数：{report['layers_used']}/24")
    print(f"节省层数：{report['layers_saved']}")
    print(f"效率得分：{report['efficiency']:.2%}")
    print(f"信念置信：{report['confidence']:.4f}")
    print(f"对齐度得分：{report['alignment_score']:.4f}")
    print(f"执行成功：{report['success']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
