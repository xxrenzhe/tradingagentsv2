# NQ 2020+ Causal Strategy Evolution

- Window: `2020-01-01` to `2026-04-28`
- Leakage audit passed: `True`
- Selected features: `24`
- Templates: `900`
- Research-pass candidates: `12`
- Best OOS candidate: `lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75`
- Best OOS net/PF: `482.528` / `2.286`
- Best pressure candidate: `lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75`
- Best 2x cost net: `416.278`

## Top Features
| feature_id | family | direction_hint | events | opportunity_score | favorable_close_rate_60m | median_mfe_60m | median_mae_60m | hit_20pt_rate_60m | adverse_10pt_rate_60m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| failed_bearish_choch_uptrend_continuation_long_us_late | smc_failed_choch_continuation | long | 143.000 | 4.787 | 60.84% | 19.500 | 13.750 | 49.65% | 61.54% |
| w_bottom_reclaim_us_rth | double_bottom | long | 1,401.000 | 4.653 | 57.74% | 29.500 | 27.250 | 65.81% | 77.59% |
| sell_pressure_absorbed_rebound_us_rth | absorption | long | 3,205.000 | 4.508 | 53.45% | 35.000 | 35.250 | 69.70% | 83.31% |
| smc_breakdown_downtrend_wave_us_rth | smc_sequence | short | 4,336.000 | 4.501 | 46.84% | 39.500 | 36.250 | 70.83% | 85.42% |
| vwap_loss_after_rally_us_rth | reclaim | short | 1,841.000 | 4.447 | 49.38% | 36.750 | 33.750 | 70.61% | 82.84% |
| displacement_pullback_continuation_long_us_rth | smc_displacement_pullback | long | 8,538.000 | 4.440 | 53.92% | 29.250 | 28.000 | 63.97% | 78.91% |
| selloff_reversal_pullback_continuation_long_us_rth | smc_sequence | long | 10,140.000 | 4.434 | 54.17% | 31.500 | 31.375 | 66.09% | 80.77% |
| trend_start_long_displacement_us_rth | trend_start | long | 8,195.000 | 4.424 | 52.63% | 30.750 | 30.000 | 64.92% | 79.94% |
| capitulation_v_reversal_long_us_late | smc_sequence | long | 814.000 | 4.417 | 54.05% | 19.750 | 16.250 | 49.88% | 65.23% |
| volume_price_bullish_mismatch_us_rth | volume_price_mismatch | long | 21,610.000 | 4.397 | 53.06% | 31.500 | 31.500 | 66.20% | 81.22% |
| low_volume_pullback_trend_short_us_rth | trend_pullback | short | 9,664.000 | 4.392 | 47.65% | 36.750 | 34.250 | 69.88% | 85.04% |
| demand_sweep_reclaim_long_us_rth | liquidity_reversal | long | 15,617.000 | 4.385 | 52.70% | 31.750 | 31.500 | 66.31% | 81.53% |

## Top Walk-Forward Candidates
| research_pass | candidate_quality | template | feature_id | family | entry_mode | stop_mode | context_filter | exit_mode | reward_risk | horizon_minutes | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_profit_factor | test_win_rate | test_payoff_ratio | test_max_drawdown_points | walk_forward_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | staged | 1.000 | 30.000 | 5.000 | 100.00% | 106.000 | 482.528 | 2.286 | 60.38% | 1.500 | 53.857 | 51.627 |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_fast_fail_rr1_h30_c5_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | bracket_fast_fail | 1.000 | 30.000 | 5.000 | 100.00% | 106.000 | 482.528 | 2.286 | 60.38% | 1.500 | 53.857 | 51.627 |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | bracket | 1.000 | 30.000 | 9.000 | 100.00% | 164.000 | 686.183 | 2.140 | 68.90% | 0.966 | 84.696 | 48.574 |
| PASS | research_candidate | lab_ict_ofs_retest_ict_bullish_ofs_ob_retest_entry_us_rth_pullback_reclaim_event_extreme_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxhigh_relative_volume_ff3_be0.5 | ict_bullish_ofs_ob_retest_entry_us_rth | ict_order_block_retest | pullback_reclaim | event_extreme | high_relative_volume | bracket | 1.500 | 60.000 | 5.000 | 80.00% | 128.000 | 628.560 | 1.357 | 46.88% | 1.538 | 208.344 | 47.552 |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_fast_fail_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | bracket_fast_fail | 1.000 | 30.000 | 8.000 | 100.00% | 193.000 | 774.818 | 2.202 | 63.73% | 1.253 | 98.923 | 46.949 |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_fast_fail_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | bracket_fast_fail | 1.000 | 30.000 | 9.000 | 100.00% | 193.000 | 767.102 | 2.176 | 63.73% | 1.238 | 98.923 | 46.552 |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | staged | 1.000 | 30.000 | 8.000 | 100.00% | 193.000 | 767.102 | 2.176 | 63.73% | 1.238 | 98.923 | 46.552 |
| PASS | research_candidate | lab_ict_ofs_retest_ict_bullish_ofs_ob_retest_entry_us_rth_pullback_reclaim_event_extreme_progress_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxhigh_relative_volume_ff3_be0.75 | ict_bullish_ofs_ob_retest_entry_us_rth | ict_order_block_retest | pullback_reclaim | event_extreme | high_relative_volume | progress_bracket | 1.500 | 60.000 | 3.000 | 66.67% | 109.000 | 392.811 | 1.396 | 49.54% | 1.422 | 218.415 | 34.712 |
| PASS | research_candidate | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_rr1_h30_c5_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | exhaustion_reversal | next_open | event_extreme | vwap_volume | bracket | 1.000 | 30.000 | 7.000 | 100.00% | 108.000 | 291.708 | 1.716 | 67.59% | 0.823 | 84.696 | 31.802 |
| PASS | research_candidate | lab_ict_ofs_retest_ict_bearish_order_flow_shift_setup_us_rth_pullback_reclaim_event_extreme_bracket_fast_fail_rr1.5_h60_c2_pb0.25_atr1.5_ctxhigh_relative_volume_ff3_be0.5 | ict_bearish_order_flow_shift_setup_us_rth | ict_order_flow_shift | pullback_reclaim | event_extreme | high_relative_volume | bracket_fast_fail | 1.500 | 60.000 | 4.000 | 75.00% | 141.000 | 368.645 | 1.259 | 29.08% | 3.072 | 306.603 | 26.868 |
| PASS | research_candidate | lab_ict_ofs_retest_ict_bearish_ofs_ob_retest_entry_us_rth_pullback_reclaim_event_extreme_progress_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxopen_trend_volume_ff3_be0.5 | ict_bearish_ofs_ob_retest_entry_us_rth | ict_order_block_retest | pullback_reclaim | event_extreme | open_trend_volume | progress_bracket | 1.500 | 60.000 | 3.000 | 66.67% | 119.000 | 93.627 | 1.067 | 42.02% | 1.473 | 315.627 | 10.674 |
| PASS | research_candidate | lab_ict_ofs_retest_ict_bullish_ofs_fvg_retest_entry_us_rth_pullback_reclaim_event_extreme_progress_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxopen_trend_volume_ff3_be0.75 | ict_bullish_ofs_fvg_retest_entry_us_rth | ict_order_flow_shift_entry | pullback_reclaim | event_extreme | open_trend_volume | progress_bracket | 1.500 | 60.000 | 5.000 | 60.00% | 63.000 | 43.350 | 1.091 | 46.03% | 1.280 | 138.332 | 10.068 |

## Top Pressure Rows
| pressure_pass | template | feature_id | selected_folds | positive_test_fold_rate | oos_trades | oos_net_points | oos_profit_factor | oos_win_rate | oos_payoff_ratio | oos_max_drawdown_points | cost_2x_net_points | cost_2x_profit_factor | cost_3x_net_points | positive_year_rate | positive_rolling_rate | min_rolling_net_points | pressure_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75 | fast_rally_fade_us_rth | 5.000 | 100.00% | 106.000 | 482.528 | 2.286 | 60.38% | 1.500 | 53.857 | 416.278 | 2.037 | 350.028 | 100.00% | 100.00% | 3.458 | 22.650 |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_fast_fail_rr1_h30_c5_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | 5.000 | 100.00% | 106.000 | 482.528 | 2.286 | 60.38% | 1.500 | 53.857 | 416.278 | 2.037 | 350.028 | 100.00% | 100.00% | 3.458 | 22.650 |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | 9.000 | 100.00% | 164.000 | 686.183 | 2.140 | 68.90% | 0.966 | 84.696 | 583.683 | 1.921 | 481.183 | 100.00% | 100.00% | 17.727 | 21.690 |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_fast_fail_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75 | fast_rally_fade_us_rth | 8.000 | 100.00% | 193.000 | 774.818 | 2.202 | 63.73% | 1.253 | 98.923 | 654.193 | 1.950 | 533.568 | 80.00% | 92.31% | -1.667 | 21.438 |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_fast_fail_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | 9.000 | 100.00% | 193.000 | 767.102 | 2.176 | 63.73% | 1.238 | 98.923 | 646.477 | 1.928 | 525.852 | 80.00% | 92.31% | -1.667 | 21.266 |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | 8.000 | 100.00% | 193.000 | 767.102 | 2.176 | 63.73% | 1.238 | 98.923 | 646.477 | 1.928 | 525.852 | 80.00% | 92.31% | -1.667 | 21.266 |
| PASS | lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_rr1_h30_c5_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75 | fast_rally_fade_us_rth | 7.000 | 100.00% | 108.000 | 291.708 | 1.716 | 67.59% | 0.823 | 84.696 | 224.208 | 1.522 | 156.708 | 100.00% | 100.00% | 28.719 | 15.039 |
| PASS | lab_ict_ofs_retest_ict_bullish_ofs_ob_retest_entry_us_rth_pullback_reclaim_event_extreme_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxhigh_relative_volume_ff3_be0.5 | ict_bullish_ofs_ob_retest_entry_us_rth | 5.000 | 80.00% | 128.000 | 628.560 | 1.357 | 46.88% | 1.538 | 208.344 | 548.560 | 1.304 | 468.560 | 100.00% | 75.00% | -73.596 | 12.185 |
| PASS | lab_ict_ofs_retest_ict_bearish_order_flow_shift_setup_us_rth_pullback_reclaim_event_extreme_bracket_fast_fail_rr1.5_h60_c2_pb0.25_atr1.5_ctxhigh_relative_volume_ff3_be0.5 | ict_bearish_order_flow_shift_setup_us_rth | 4.000 | 75.00% | 141.000 | 368.645 | 1.259 | 29.08% | 3.072 | 306.603 | 280.520 | 1.189 | 192.395 | 100.00% | 80.00% | -98.755 | 9.492 |
| PASS | lab_ict_ofs_retest_ict_bullish_ofs_ob_retest_entry_us_rth_pullback_reclaim_event_extreme_progress_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxhigh_relative_volume_ff3_be0.75 | ict_bullish_ofs_ob_retest_entry_us_rth | 3.000 | 66.67% | 109.000 | 392.811 | 1.396 | 49.54% | 1.422 | 218.415 | 324.686 | 1.316 | 256.561 | 100.00% | 50.00% | -122.282 | 8.969 |
| PASS | lab_ict_ofs_retest_ict_bullish_ofs_fvg_retest_entry_us_rth_pullback_reclaim_event_extreme_progress_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxopen_trend_volume_ff3_be0.75 | ict_bullish_ofs_fvg_retest_entry_us_rth | 5.000 | 60.00% | 63.000 | 43.350 | 1.091 | 46.03% | 1.280 | 138.332 | 3.975 | 1.008 | -35.400 | 66.67% | 83.33% | -3.705 | 6.929 |
| PASS | lab_ict_ofs_retest_ict_bearish_ofs_ob_retest_entry_us_rth_pullback_reclaim_event_extreme_progress_bracket_rr1.5_h60_c2_pb0.25_atr1.5_ctxopen_trend_volume_ff3_be0.5 | ict_bearish_ofs_ob_retest_entry_us_rth | 3.000 | 66.67% | 119.000 | 93.627 | 1.067 | 42.02% | 1.473 | 315.627 | 19.252 | 1.013 | -55.123 | 33.33% | 50.00% | -76.744 | 5.871 |

## Review Summary
{
  "next_evolution_steps": [
    {
      "action": "围绕fast_rally_fade_us_rth做一条主线强化",
      "details": [
        "保留 next_open + event_extreme + RR1 + vwap_volume 作为主骨架",
        "微调 fast_fail bars=2/3/4/5 与确认条件强弱",
        "增加开盘时段、趋势日/均值回归日分类过滤",
        "测试 partial at 0.75R / remainder at 1.25R，而不是只做纯RR1"
      ],
      "goal": "把当前最稳健候选打磨成可投产版本。",
      "priority": 1
    },
    {
      "action": "强化w_bottom_reclaim_us_rth与sell_pressure_absorbed_rebound_us_rth的合成过滤",
      "details": [
        "将双底回收与吸收型量价背离做交集或顺序确认",
        "要求 reclaim 后保持VWAP上方1-3 bars",
        "排除反弹发生在高波动连续破底日的情形"
      ],
      "goal": "把selected_folds从1-2提升到3+，验证是否能进入research_pass。",
      "priority": 2
    },
    {
      "action": "针对bos_stair_step_continuation_short_us_rth开发专属 continuation 模板",
      "details": [
        "不要直接追空，改成 bounce reject + re-break entry",
        "止损放在反弹高点/失效原点，而不是统一ATR硬止损",
        "加入US RTH与VWAP下方约束",
        "测试时间退出30/45/60分钟和结构 trailing"
      ],
      "goal": "把强特征转成可验证策略。",
      "priority": 3
    },
    {
      "action": "削减ICT策略搜索空间，转向结构性修复而非继续广撒网",
      "details": [
        "淘汰PF<1.15且3x成本转负的模板家族",
        "减少progress_bracket泛化模板",
        "只保留通过research_pass或接近通过、且OOS trades>=100的ICT分支"
      ],
      "goal": "避免继续在低稳定性高自由度空间过拟合。",
      "priority": 4
    },
    {
      "action": "对watch级爆发表现做regime归因",
      "details": [
        "检查fast_selloff_rebound_us_rth是否集中于单一高波动年份",
        "按VIX代理、开盘区间、当日趋势强度、午后反转环境分层",
        "若只在少数regime有效，则改成条件激活子策略"
      ],
      "goal": "把‘看起来强’转化为‘在哪些环境下强’。",
      "priority": 5
    }
  ],
  "production_readiness": {
    "entry_policy_safe": true,
    "leakage_audit_passed": true,
    "not_ready": [
      {
        "reason": "selected_folds不足，research_pass=false",
        "template_family": "fast_selloff_rebound_us_rth variants"
      },
      {
        "reason": "稳定性弱、回撤深、成本后边际薄",
        "template_family": "most ICT progress_bracket variants"
      },
      {
        "reason": "无法证明跨期泛化",
        "template_family": "single-fold watch candidates"
      }
    ],
    "overall_assessment": "目前只有fast_rally_fade_us_rth这一条反转做空主线接近生产标准；其余多数仍处于强化研究阶段。",
    "ready_now": [
      {
        "status": "paper_trade_or_shadow_live",
        "template": "lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75"
      },
      {
        "status": "paper_trade_or_shadow_live",
        "template": "lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_bracket_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75"
      }
    ],
    "same_bar_policy_conservative": true
  },
  "risk_principles": [
    "优先相信purged walk-forward，而不是全样本净值。",
    "selected_folds少于3、OOS trades少于60的策略，不进入生产候选。",
    "成本压力必须至少看3x；3x后PF接近1或净值转负的，默认淘汰。",
    "年度稳定性和滚动稳定性必须同时观察，不能只看总OOS为正。",
    "对低胜率高赔率策略，重点看最差折、最差滚动和中位数交易，而不是均值。",
    "高共线模板只保留一个主执行版本，避免同一alpha重复下注。",
    "先做简单、可解释、审计清晰的执行逻辑，再增加复杂出场。"
  ],
  "summary": {
    "best_market_features": [
      "fast_rally_fade_us_rth",
      "w_bottom_reclaim_us_rth",
      "fast_selloff_rebound_us_rth",
      "sell_pressure_absorbed_rebound_us_rth",
      "ict_bullish_ofs_ob_retest_entry_us_rth",
      "ict_bearish_order_flow_shift_setup_us_rth",
      "bos_stair_step_continuation_short_us_rth",
      "displacement_pullback_continuation_long_us_rth"
    ],
    "decision": {
      "eliminate_or_deprioritize": [
        "ict_bullish_ofs_fvg_retest_entry_us_rth progress_bracket",
        "ict_bearish_ofs_ob_retest_entry_us_rth progress_bracket",
        "broad ICT template sprawl without fold stability"
      ],
      "promote": [
        "fast_rally_fade_us_rth family"
      ],
      "reinforce": [
        "w_bottom_reclaim_us_rth",
        "sell_pressure_absorbed_rebound_us_rth",
        "bos_stair_step_continuation_short_us_rth",
        "displacement_pullback_continuation_long_us_rth"
      ]
    },
    "key_conclusion": "严格因果标准下，真正站得住的只有 fast_rally_fade_us_rth 做空急涨衰竭反转主线。双底回收、吸收反弹和部分快速下杀反弹特征有潜质，但当前还缺少足够WF折数验证。多数ICT结构虽然全样本赚钱，甚至OOS总和为正，但在最差折、滚动稳定性与成本缓冲上仍不够，不能因为漂亮的总收益曲线就晋级。"
  }
}