"""
排序模块测试
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.ranking.base_ranker import BaseRanker
from backend.ranking.rule_ranker import RuleBasedRanker
from backend.ranking.business_filter import BusinessFilter
from backend.ranking.diversity_controller import DiversityController
from backend.ranking.ranking_strategy import RankingStrategy


class TestRuleBasedRanker:
    """规则排序器测试"""
    
    @pytest.mark.asyncio
    async def test_rank_empty_candidates(self):
        """测试空候选集排序"""
        ranker = RuleBasedRanker()
        
        # Mock feature store
        ranker.feature_store = AsyncMock()
        
        result = await ranker.rank([], user_id=1)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_rank_with_candidates(self):
        """测试候选集排序"""
        ranker = RuleBasedRanker()
        
        # Mock feature store
        ranker.feature_store = AsyncMock()
        ranker.feature_store.get_user_sequence.return_value = [1, 2, 3]
        ranker.feature_store.get_game_metadata.return_value = {
            "genres": ["Action", "Adventure"],
            "metascore": 85,
            "developer": "Test Studio",
            "release_date": "2023-01-01"
        }
        
        candidates = [(1, 0.8), (2, 0.6), (3, 0.7)]
        
        result = await ranker.rank(candidates, user_id=1)
        
        # 应该返回排序后的结果
        assert len(result) == 3
        assert all(isinstance(item_id, int) and isinstance(score, float) 
                  for item_id, score in result)
    
    def test_update_weights(self):
        """测试更新权重"""
        ranker = RuleBasedRanker()
        
        new_weights = {"recall_score": 0.6, "genre_match": 0.4}
        ranker.update_weights(new_weights)
        
        assert ranker.weights["recall_score"] == 0.6
        assert ranker.weights["genre_match"] == 0.4


class TestBusinessFilter:
    """业务过滤器测试"""
    
    @pytest.mark.asyncio
    async def test_filter_empty_candidates(self):
        """测试空候选集过滤"""
        filter_obj = BusinessFilter()
        
        # Mock feature store
        filter_obj.feature_store = AsyncMock()
        
        result = await filter_obj.filter([], user_id=1)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_filter_played_games(self):
        """测试过滤已玩游戏"""
        filter_obj = BusinessFilter()
        
        # Mock feature store
        filter_obj.feature_store = AsyncMock()
        filter_obj.feature_store.get_user_sequence.return_value = [1, 2]  # 用户已玩游戏
        filter_obj.feature_store.get_game_metadata.return_value = {
            "developer": "Test Studio",
            "genres": ["Action"]
        }
        
        candidates = [(1, 0.8), (2, 0.6), (3, 0.7)]  # 游戏1和2已玩过
        
        result = await filter_obj.filter(candidates, user_id=1)
        
        # 应该只返回游戏3
        assert len(result) == 1
        assert result[0][0] == 3
    
    def test_update_filter_rules(self):
        """测试更新过滤规则"""
        filter_obj = BusinessFilter()
        
        filter_obj.update_filter_rules(max_same_developer=3, max_same_genre=4)
        
        assert filter_obj.max_same_developer == 3
        assert filter_obj.max_same_genre == 4


class TestDiversityController:
    """多样性控制器测试"""
    
    @pytest.mark.asyncio
    async def test_diversity_control_empty_candidates(self):
        """测试空候选集多样性控制"""
        controller = DiversityController()
        
        # Mock feature store
        controller.feature_store = AsyncMock()
        
        result = await controller.apply_diversity_control([], user_id=1)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_diversity_control_few_candidates(self):
        """测试少量候选集多样性控制"""
        controller = DiversityController()
        
        # Mock feature store
        controller.feature_store = AsyncMock()
        controller.feature_store.get_game_metadata.return_value = {
            "genres": ["Action"],
            "developer": "Test Studio",
            "price": 29.99,
            "release_date": "2023-01-01"
        }
        
        candidates = [(1, 0.8), (2, 0.6)]
        
        result = await controller.apply_diversity_control(candidates, user_id=1)
        
        # 少于窗口大小，应该直接返回
        assert len(result) == 2
        assert result == candidates
    
    def test_update_diversity_parameters(self):
        """测试更新多样性参数"""
        controller = DiversityController()
        
        controller.update_diversity_parameters(
            genre_weight=0.4,
            developer_weight=0.3,
            diversity_window=10
        )
        
        assert controller.genre_diversity_weight == 0.4
        assert controller.developer_diversity_weight == 0.3
        assert controller.diversity_window == 10


class TestRankingStrategy:
    """排序策略测试"""
    
    @pytest.mark.asyncio
    async def test_rank_and_filter_empty_candidates(self):
        """测试空候选集排序和过滤"""
        strategy = RankingStrategy()
        
        # Mock components
        strategy.rule_ranker = AsyncMock()
        strategy.business_filter = AsyncMock()
        strategy.diversity_controller = AsyncMock()
        
        result = await strategy.rank_and_filter([], user_id=1)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_rank_and_filter_with_candidates(self):
        """测试候选集排序和过滤"""
        strategy = RankingStrategy()
        
        # Mock components
        strategy.rule_ranker = AsyncMock()
        strategy.business_filter = AsyncMock()
        strategy.diversity_controller = AsyncMock()
        
        # 设置mock返回值
        candidates = [(1, 0.8), (2, 0.6), (3, 0.7)]
        strategy.rule_ranker.rank.return_value = candidates
        strategy.business_filter.filter.return_value = candidates[:2]
        strategy.diversity_controller.apply_diversity_control.return_value = candidates[:2]
        
        result = await strategy.rank_and_filter(candidates, user_id=1)
        
        # 验证调用了所有组件
        strategy.rule_ranker.rank.assert_called_once()
        strategy.business_filter.filter.assert_called_once()
        strategy.diversity_controller.apply_diversity_control.assert_called_once()
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_different_strategies(self):
        """测试不同排序策略"""
        strategy = RankingStrategy()
        
        # Mock components
        strategy.rule_ranker = AsyncMock()
        strategy.business_filter = AsyncMock()
        strategy.diversity_controller = AsyncMock()
        
        candidates = [(1, 0.8), (2, 0.6)]
        strategy.rule_ranker.rank.return_value = candidates
        strategy.business_filter.filter.return_value = candidates
        strategy.diversity_controller.apply_diversity_control.return_value = candidates
        
        # 测试不同策略
        strategies = ["default", "diversity_focused", "quality_focused"]
        
        for strat in strategies:
            result = await strategy.rank_and_filter(candidates, user_id=1, strategy=strat)
            assert len(result) == 2
    
    def test_update_ranking_config(self):
        """测试更新排序配置"""
        strategy = RankingStrategy()
        
        # Mock components
        strategy.rule_ranker = MagicMock()
        strategy.business_filter = MagicMock()
        strategy.diversity_controller = MagicMock()
        
        config = {
            "ranking_weights": {"recall_score": 0.6},
            "filter_rules": {"max_same_developer": 3},
            "diversity_params": {"genre_weight": 0.4}
        }
        
        strategy.update_ranking_config(**config)
        
        # 验证调用了更新方法
        strategy.rule_ranker.update_weights.assert_called_once()
        strategy.business_filter.update_filter_rules.assert_called_once()
        strategy.diversity_controller.update_diversity_parameters.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
