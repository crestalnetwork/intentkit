"""
意图 Schema 扩展 - 支持信念探针集成
Intent Schema Extension for Belief Probe Integration

日期：2026-03-07
作者：Claw (OpenClaw)
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class BeliefConfig(BaseModel):
    """信念探针配置"""
    
    # 置信度阈值 (0-1)
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="早退置信度阈值"
    )
    
    # 最小连续高置信层数
    min_consecutive_layers: int = Field(
        default=3,
        ge=1,
        le=24,
        description="触发早退的最小连续高置信层数"
    )
    
    # 是否启用早退
    early_exit_enabled: bool = Field(
        default=True,
        description="是否启用早退机制"
    )
    
    # 最小层数 (即使置信度高也至少运行的层数)
    min_layers: int = Field(
        default=5,
        ge=1,
        le=24,
        description="最小执行层数"
    )
    
    # 最大层数 (即使置信度低也最多运行的层数)
    max_layers: int = Field(
        default=24,
        ge=1,
        le=24,
        description="最大执行层数"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "confidence_threshold": 0.8,
                "min_consecutive_layers": 3,
                "early_exit_enabled": True,
                "min_layers": 5,
                "max_layers": 24
            }
        }


class SuccessCriteria(BaseModel):
    """成功标准定义"""
    
    # 意图达成标志
    intent_achieved: bool = Field(
        ...,
        description="意图是否达成"
    )
    
    # 信念置信度
    belief_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="信念探针置信度"
    )
    
    # 使用的层数
    layers_used: int = Field(
        ...,
        ge=1,
        le=24,
        description="实际使用的层数"
    )
    
    # 效率得分
    efficiency_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="效率得分 (1 - layers_used/24)"
    )
    
    # 对齐度得分
    alignment_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="意图 - 信念对齐度得分"
    )


class EnhancedIntentSchema(BaseModel):
    """增强意图 Schema - 支持信念探针"""
    
    # 基础字段
    name: str = Field(..., description="意图名称")
    description: str = Field(..., description="意图描述")
    
    # 参数定义 (JSON Schema 格式)
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="参数定义"
    )
    
    # 信念探针配置
    belief_config: BeliefConfig = Field(
        default_factory=BeliefConfig,
        description="信念探针配置"
    )
    
    # 成功标准
    success_criteria: SuccessCriteria = Field(
        default=None,
        description="成功标准 (执行后填充)"
    )
    
    # 执行结果
    execution_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="执行结果"
    )
    
    def calculate_alignment(self) -> float:
        """计算意图 - 信念对齐度
        
        对齐度 = 0.5 * 意图达成 + 0.3 * 信念置信 + 0.2 * 效率
        """
        if not self.success_criteria:
            return 0.0
        
        # 意图达成度 (0 或 1)
        intent_achievement = 1.0 if self.success_criteria.intent_achieved else 0.0
        
        # 信念置信度 (0-1)
        belief_confidence = self.success_criteria.belief_confidence
        
        # 效率得分 (早退奖励)
        efficiency = 1 - (self.success_criteria.layers_used / 24)
        
        # 综合对齐度
        alignment = (
            0.5 * intent_achievement +
            0.3 * belief_confidence +
            0.2 * efficiency
        )
        
        self.success_criteria.alignment_score = alignment
        self.success_criteria.efficiency_score = efficiency
        
        return alignment
    
    @classmethod
    def create_search_intent(cls) -> "EnhancedIntentSchema":
        """创建搜索意图示例"""
        return cls(
            name="search",
            description="搜索信息",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "source": {"type": "string", "description": "搜索来源 (可选)"}
                },
                "required": ["query"]
            },
            belief_config=BeliefConfig(
                confidence_threshold=0.8,
                min_consecutive_layers=3,
                early_exit_enabled=True,
                min_layers=5
            )
        )
    
    @classmethod
    def create_math_intent(cls) -> "EnhancedIntentSchema":
        """创建数学计算意图示例"""
        return cls(
            name="math_calculation",
            description="数学计算",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"},
                    "precision": {"type": "integer", "description": "精度 (小数位数)"}
                },
                "required": ["expression"]
            },
            belief_config=BeliefConfig(
                confidence_threshold=0.9,  # 数学计算需要更高置信度
                min_consecutive_layers=4,
                early_exit_enabled=True,
                min_layers=8  # 数学计算需要更多层
            )
        )
    
    @classmethod
    def create_creative_intent(cls) -> "EnhancedIntentSchema":
        """创建创意写作意图示例"""
        return cls(
            name="creative_writing",
            description="创意写作",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "主题"},
                    "style": {"type": "string", "description": "写作风格"},
                    "length": {"type": "integer", "description": "长度 (字数)"}
                },
                "required": ["topic"]
            },
            belief_config=BeliefConfig(
                confidence_threshold=0.7,  # 创意任务可以降低阈值
                min_consecutive_layers=2,
                early_exit_enabled=True,
                min_layers=3  # 创意任务可以更早退出
            )
        )


if __name__ == "__main__":
    # 测试示例
    print("=== 意图 Schema 扩展测试 ===\n")
    
    # 创建搜索意图
    search_intent = EnhancedIntentSchema.create_search_intent()
    print(f"搜索意图：{search_intent.name}")
    print(f"描述：{search_intent.description}")
    print(f"置信度阈值：{search_intent.belief_config.confidence_threshold}")
    print()
    
    # 创建数学意图
    math_intent = EnhancedIntentSchema.create_math_intent()
    print(f"数学意图：{math_intent.name}")
    print(f"置信度阈值：{math_intent.belief_config.confidence_threshold}")
    print()
    
    # 创建创意意图
    creative_intent = EnhancedIntentSchema.create_creative_intent()
    print(f"创意意图：{creative_intent.name}")
    print(f"置信度阈值：{creative_intent.belief_config.confidence_threshold}")
