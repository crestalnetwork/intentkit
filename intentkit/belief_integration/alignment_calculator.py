"""
意图 - 信念对齐度计算
Intent-Belief Alignment Calculator

日期：2026-03-07
作者：Claw (OpenClaw)
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AlignmentResult:
    """对齐度计算结果"""
    
    # 综合对齐度 (0-1)
    alignment_score: float
    
    # 意图达成度 (0 或 1)
    intent_achievement: float
    
    # 信念置信度 (0-1)
    belief_confidence: float
    
    # 效率得分 (0-1)
    efficiency: float
    
    # 各组件权重
    weights: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "alignment_score": self.alignment_score,
            "intent_achievement": self.intent_achievement,
            "belief_confidence": self.belief_confidence,
            "efficiency": self.efficiency,
            "weights": self.weights
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"对齐度：{self.alignment_score:.4f}\n"
            f"  - 意图达成：{self.intent_achievement:.4f} (权重 {self.weights['intent']:.1%})\n"
            f"  - 信念置信：{self.belief_confidence:.4f} (权重 {self.weights['belief']:.1%})\n"
            f"  - 效率得分：{self.efficiency:.4f} (权重 {self.weights['efficiency']:.1%})"
        )


class AlignmentCalculator:
    """对齐度计算器"""
    
    # 默认权重
    DEFAULT_WEIGHTS = {
        "intent": 0.5,      # 意图达成 50%
        "belief": 0.3,      # 信念置信 30%
        "efficiency": 0.2   # 效率奖励 20%
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """初始化计算器
        
        Args:
            weights: 自定义权重 (可选)
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
    
    def calculate(
        self,
        intent_achieved: bool,
        belief_confidence: float,
        layers_used: int,
        total_layers: int = 24
    ) -> AlignmentResult:
        """计算对齐度
        
        Args:
            intent_achieved: 意图是否达成
            belief_confidence: 信念置信度 (0-1)
            layers_used: 实际使用层数
            total_layers: 总层数 (默认 24)
            
        Returns:
            对齐度计算结果
        """
        # 意图达成度 (0 或 1)
        intent_score = 1.0 if intent_achieved else 0.0
        
        # 效率得分 (早退奖励)
        efficiency = 1 - (layers_used / total_layers)
        
        # 综合对齐度
        alignment = (
            self.weights["intent"] * intent_score +
            self.weights["belief"] * belief_confidence +
            self.weights["efficiency"] * efficiency
        )
        
        return AlignmentResult(
            alignment_score=alignment,
            intent_achievement=intent_score,
            belief_confidence=belief_confidence,
            efficiency=efficiency,
            weights=self.weights
        )
    
    def calculate_batch(
        self,
        executions: list
    ) -> Dict[str, float]:
        """批量计算对齐度
        
        Args:
            executions: 执行列表，每项包含：
                - intent_achieved: bool
                - belief_confidence: float
                - layers_used: int
                
        Returns:
            统计字典
        """
        if not executions:
            return {"avg_alignment": 0.0, "count": 0}
        
        results = []
        for exec_data in executions:
            result = self.calculate(
                intent_achieved=exec_data["intent_achieved"],
                belief_confidence=exec_data["belief_confidence"],
                layers_used=exec_data["layers_used"]
            )
            results.append(result.alignment_score)
        
        return {
            "avg_alignment": sum(results) / len(results),
            "min_alignment": min(results),
            "max_alignment": max(results),
            "std_alignment": (sum((x - sum(results)/len(results))**2 for x in results) / len(results)) ** 0.5,
            "count": len(results)
        }


def demo():
    """演示使用"""
    print("=== 意图 - 信念对齐度计算演示 ===\n")
    
    # 创建计算器
    calculator = AlignmentCalculator()
    
    # 示例 1: 早退成功
    print("示例 1: 早退成功")
    result1 = calculator.calculate(
        intent_achieved=True,
        belief_confidence=0.92,
        layers_used=12
    )
    print(result1)
    print()
    
    # 示例 2: 全模型成功
    print("示例 2: 全模型成功")
    result2 = calculator.calculate(
        intent_achieved=True,
        belief_confidence=0.95,
        layers_used=24
    )
    print(result2)
    print()
    
    # 示例 3: 早退失败
    print("示例 3: 早退失败")
    result3 = calculator.calculate(
        intent_achieved=False,
        belief_confidence=0.85,
        layers_used=8
    )
    print(result3)
    print()
    
    # 批量计算
    print("=== 批量统计 ===")
    executions = [
        {"intent_achieved": True, "belief_confidence": 0.92, "layers_used": 12},
        {"intent_achieved": True, "belief_confidence": 0.95, "layers_used": 24},
        {"intent_achieved": False, "belief_confidence": 0.85, "layers_used": 8},
        {"intent_achieved": True, "belief_confidence": 0.88, "layers_used": 15},
        {"intent_achieved": True, "belief_confidence": 0.91, "layers_used": 10},
    ]
    
    stats = calculator.calculate_batch(executions)
    print(f"平均对齐度：{stats['avg_alignment']:.4f}")
    print(f"最小对齐度：{stats['min_alignment']:.4f}")
    print(f"最大对齐度：{stats['max_alignment']:.4f}")
    print(f"标准差：{stats['std_alignment']:.4f}")
    print(f"样本数：{stats['count']}")


if __name__ == "__main__":
    demo()
