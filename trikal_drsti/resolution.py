from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .core import ViewConclusion, Sentiment

@dataclass
class Conflict:
    """Represents a disagreement between two views."""
    views_involved: List[str]
    description: str
    severity: float # 0.0 to 1.0
    conflict_type: str  # "semantic", "directional", "confidence"

@dataclass
class FinalDecision:
    """The resolved output from the system."""
    primary_conclusion: ViewConclusion
    conflicts: List[Conflict]
    explanation: str
    ruling_basis: str  # "precedence", "confidence", "override", "uncertainty"
    suppressed_views: List[tuple]  # [(view_name, reason)]
    system_state: str  # "STABLE", "CONTESTED", "FRAGILE", "PRECARIOUS", "CRITICAL"
    counterfactual_thresholds: List[str]  # What would flip this ruling
    robustness_warning: Optional[str] = None  # "Rational under model" vs "Robust under uncertainty"

class ConflictDetector:
    """Detects SEMANTIC contradictions between temporal views."""
    
    # Define semantic incompatibilities
    CRITICAL_RISKS = {Sentiment.CRASH, Sentiment.SPIKE, Sentiment.OVEREXTENDED_HIGH, Sentiment.OVEREXTENDED_LOW}
    STABLE_STATES = {Sentiment.STABLE}
    TRENDING = {Sentiment.UPTREND, Sentiment.DOWNTREND}
    
    def detect(self, conclusions: List[ViewConclusion]) -> List[Conflict]:
        conflicts = []
        by_scale = {c.time_scale: c for c in conclusions}
        
        short = by_scale.get("Short")
        mid = by_scale.get("Mid")
        long_term = by_scale.get("Long")

        # 1. SEMANTIC CONFLICT: Risk signal vs Calm assessment
        # This is a conflict regardless of which "wins"
        if short and mid:
            if short.sentiment in self.CRITICAL_RISKS and mid.sentiment in self.STABLE_STATES:
                conflicts.append(Conflict(
                    views_involved=["Short", "Mid"],
                    description=f"Short-term detects {short.sentiment.value} (immediate danger) while Mid-term shows {mid.sentiment.value} (no threat detected).",
                    severity=0.9,
                    conflict_type="semantic"
                ))
            elif mid.sentiment in self.CRITICAL_RISKS and short.sentiment in self.STABLE_STATES:
                conflicts.append(Conflict(
                    views_involved=["Short", "Mid"],
                    description=f"Mid-term trend shows {mid.sentiment.value} but Short-term reads {short.sentiment.value} (temporal mismatch).",
                    severity=0.7,
                    conflict_type="semantic"
                ))

        if short and long_term:
            if short.sentiment in self.CRITICAL_RISKS and long_term.sentiment in self.STABLE_STATES:
                conflicts.append(Conflict(
                    views_involved=["Short", "Long"],
                    description=f"Short-term spike ({short.sentiment.value}) occurs within structurally stable baseline. Noise or anomaly?",
                    severity=0.6,
                    conflict_type="semantic"
                ))
            elif long_term.sentiment in self.CRITICAL_RISKS and short.sentiment in self.STABLE_STATES:
                conflicts.append(Conflict(
                    views_involved=["Short", "Long"],
                    description=f"Long-term structural risk ({long_term.sentiment.value}) not reflected in short-term readings. Lagging indicator or false structural read?",
                    severity=0.8,
                    conflict_type="semantic"
                ))

        # 2. DIRECTIONAL CONFLICT: Opposing momentum
        if short and mid:
            if short.sentiment == Sentiment.UPTREND and mid.sentiment == Sentiment.DOWNTREND:
                conflicts.append(Conflict(
                    views_involved=["Short", "Mid"],
                    description="Short-term reversal (UPTREND) contradicts Mid-term decline (DOWNTREND). Temporary bounce or trend shift?",
                    severity=0.65,
                    conflict_type="directional"
                ))
            elif short.sentiment == Sentiment.DOWNTREND and mid.sentiment == Sentiment.UPTREND:
                conflicts.append(Conflict(
                    views_involved=["Short", "Mid"],
                    description="Short-term pullback (DOWNTREND) within Mid-term rally (UPTREND). Correction or reversal?",
                    severity=0.65,
                    conflict_type="directional"
                ))

        # 3. STRUCTURAL CONTRADICTION: Trend pushing into limits
        if mid and long_term:
            if mid.sentiment in self.TRENDING and long_term.sentiment in self.CRITICAL_RISKS:
                conflicts.append(Conflict(
                    views_involved=["Mid", "Long"],
                    description=f"Mid-term momentum ({mid.sentiment.value}) pushing into Long-term structural boundary ({long_term.sentiment.value}). Mean reversion imminent or breakout?",
                    severity=0.95,
                    conflict_type="semantic"
                ))

        # 4. CONFIDENCE CONFLICT: High confidence disagreement
        for i, c1 in enumerate(conclusions):
            for c2 in conclusions[i+1:]:
                if c1.sentiment != c2.sentiment and c1.confidence > 0.7 and c2.confidence > 0.7:
                    conflicts.append(Conflict(
                        views_involved=[c1.time_scale, c2.time_scale],
                        description=f"{c1.time_scale} strongly believes {c1.sentiment.value} ({c1.confidence:.0%}) while {c2.time_scale} strongly believes {c2.sentiment.value} ({c2.confidence:.0%}). Irreconcilable difference.",
                        severity=0.85,
                        conflict_type="confidence"
                    ))
        
        return conflicts

@dataclass
class ViewWeightConfig:
    weights: Dict[str, float] = field(default_factory=lambda: {"Short": 0.5, "Mid": 1.0, "Long": 1.5})


class ResolutionEngine:
    """Makes CONSEQUENCE-AWARE precedence rulings with counterfactuals."""
    
    # Loss multipliers: cost of being wrong at each timescale
    LOSS_MULTIPLIERS = {
        "Short": 3.0,  # Short-term crashes are often irreversible
        "Mid": 1.5,    # Mid-term trends can be corrected
        "Long": 1.0    # Long-term structural issues are slowest to materialize
    }
    
    # Urgency multipliers for critical sentiments
    URGENCY_BOOST = {
        Sentiment.CRASH: 2.5,
        Sentiment.SPIKE: 1.8,
        Sentiment.OVEREXTENDED_HIGH: 1.5,
        Sentiment.OVEREXTENDED_LOW: 1.5,
    }
    
    def __init__(self, config: ViewWeightConfig = None):
        self.config = config if config else ViewWeightConfig()
        # Cumulative pressure tracking
        self.short_term_warnings = []  # [(timestamp, confidence, sentiment)]
        self.long_term_override_count = 0
        self.structural_legitimacy = 1.0  # Degrades when Long is repeatedly contradicted

    def resolve(self, conclusions: List[ViewConclusion], conflicts: List[Conflict]) -> FinalDecision:
        """
        CONSEQUENCE-AWARE adjudication with:
        - Cumulative pressure tracking (not just single thresholds)
        - Structural legitimacy degradation (Long can lose credibility)
        - System state taxonomy (STABLE/CONTESTED/FRAGILE/PRECARIOUS/CRITICAL)
        - Robustness warnings (rational ≠ robust)
        """
        
        by_scale = {c.time_scale: c for c in conclusions}
        short = by_scale.get("Short")
        mid = by_scale.get("Mid")
        long_term = by_scale.get("Long")
        
        suppressed = []
        counterfactuals = []
        robustness_warning = None
        
        # Track short-term warnings for cumulative pressure
        if short and short.sentiment in {Sentiment.CRASH, Sentiment.SPIKE} and short.confidence > 0.65:
            self.short_term_warnings.append((short.sentiment, short.confidence))
            # Keep last 10 warnings
            self.short_term_warnings = self.short_term_warnings[-10:]
        
        # Calculate cumulative pressure: multiple 70% warnings > single 80% warning
        cumulative_pressure = 0.0
        if len(self.short_term_warnings) >= 3:
            # Clustering: 3+ warnings in recent history
            avg_confidence = sum(w[1] for w in self.short_term_warnings[-5:]) / min(5, len(self.short_term_warnings))
            cumulative_pressure = avg_confidence * (len(self.short_term_warnings) / 5.0)  # Scale by density
        
        # RULE 1: Immediate irreversible danger OR cumulative pressure threshold
        emergency_override = False
        if short and short.sentiment == Sentiment.CRASH and short.confidence > 0.75:
            emergency_override = True
            explanation = f"EMERGENCY OVERRIDE: Short-term CRASH at {short.confidence:.0%}. Irreversible loss imminent."
        elif cumulative_pressure > 0.75:
            emergency_override = True
            explanation = f"CUMULATIVE PRESSURE OVERRIDE: {len(self.short_term_warnings)} persistent warnings (avg {cumulative_pressure:.0%}). Pattern indicates sustained threat."
        
        if emergency_override:
            if mid:
                suppressed.append((mid.time_scale, f"Mid-term {mid.sentiment.value} irrelevant during acute crisis"))
            if long_term:
                suppressed.append((long_term.time_scale, f"Long-term {long_term.sentiment.value} too slow to prevent immediate catastrophe"))
                # Degrade structural legitimacy when overridden
                self.long_term_override_count += 1
                self.structural_legitimacy = max(0.1, 1.0 - (self.long_term_override_count * 0.1))
            
            counterfactuals.append(f"No counterfactual - emergency protocol active")
            system_state = "CRITICAL"
            robustness_warning = "Emergency override is rational under model. Robustness: UNKNOWN (no time for validation)"
            
            return FinalDecision(
                primary_conclusion=short,
                conflicts=conflicts,
                explanation=explanation,
                ruling_basis="override",
                suppressed_views=suppressed,
                system_state=system_state,
                counterfactual_thresholds=counterfactuals,
                robustness_warning=robustness_warning
            )
        
        # RULE 2: Structural limits (but apply legitimacy degradation)
        structural_score = self.structural_legitimacy  # Start with current legitimacy
        if long_term and long_term.sentiment in {Sentiment.OVEREXTENDED_HIGH, Sentiment.OVEREXTENDED_LOW}:
            structural_score *= long_term.confidence
            
            # Check if structure is degrading (multiple overrides = loss of legitimacy)
            if self.long_term_override_count > 3:
                explanation = f"STRUCTURAL DEGRADATION WARNING: Long-term boundary ({long_term.sentiment.value}) has been overridden {self.long_term_override_count} times. Legitimacy: {self.structural_legitimacy:.0%}"
                robustness_warning = f"Long-term structure may be breaking down. Rational to follow structure, but robustness is DEGRADED."
            else:
                explanation = f"STRUCTURAL PRECEDENCE: Long-term boundary ({long_term.sentiment.value} at {long_term.confidence:.0%}, legitimacy {self.structural_legitimacy:.0%})."
                robustness_warning = "Rational under mean-reversion model. Robustness depends on structural stability assumption."
            
            # Apply structural ruling if legitimacy is sufficient
            if structural_score > 0.5:
                if mid and mid.sentiment in {Sentiment.UPTREND, Sentiment.DOWNTREND}:
                    suppressed.append((mid.time_scale, f"Mid-term {mid.sentiment.value} overridden - pushing into structural limit"))
                if short:
                    suppressed.append((short.time_scale, f"Short-term {short.sentiment.value} noise filtered"))
                
                # Counterfactuals
                needed_conf = (0.5 / self.structural_legitimacy) if self.structural_legitimacy > 0 else 0.95
                counterfactuals.append(f"Mid-term would need {min(0.95, needed_conf):.0%}+ to override (legitimacy-adjusted)")
                counterfactuals.append(f"Short-term emergency at 75%+ would override")
                counterfactuals.append(f"Or: 3+ persistent Short warnings at 70%+ (cumulative pressure)")
                
                # System state based on conflicts + legitimacy
                if len(conflicts) > 5 or self.structural_legitimacy < 0.7:
                    system_state = "PRECARIOUS"
                elif len(conflicts) > 2:
                    system_state = "FRAGILE"
                elif len(conflicts) > 0:
                    system_state = "CONTESTED"
                else:
                    system_state = "STABLE"
                
                return FinalDecision(
                    primary_conclusion=long_term,
                    conflicts=conflicts,
                    explanation=explanation,
                    ruling_basis="precedence",
                    suppressed_views=suppressed,
                    system_state=system_state,
                    counterfactual_thresholds=counterfactuals,
                    robustness_warning=robustness_warning
                )
            else:
                # Structural legitimacy too low - fall through to consequence scoring
                explanation = f"Structural legitimacy collapsed ({self.structural_legitimacy:.0%}). Falling back to consequence scoring."
                robustness_warning = "Structure has lost credibility. Model assumptions may be breaking."
        
        # RULE 3: Low confidence across all views (uncertainty flagging)
        max_confidence = max(c.confidence for c in conclusions)
        if max_confidence < 0.5:
            scores = [(c.confidence * self.config.weights.get(c.time_scale, 1.0), c) for c in conclusions]
            scores.sort(key=lambda x: x[0], reverse=True)
            best = scores[0][1]
            
            explanation = f"UNCERTAINTY: All views low confidence (max {max_confidence:.0%}). Defaulting to {best.time_scale} but DO NOT TRUST."
            robustness_warning = "Rational to pick highest score, but robustness: NONE. No view has conviction."
            
            for score, c in scores[1:]:
                suppressed.append((c.time_scale, f"{c.sentiment.value} ({c.confidence:.0%}) equally uncertain"))
            
            counterfactuals.append(f"Any view reaching 60%+ confidence would dominate")
            system_state = "CONTESTED"  # Low confidence = contested by default
            
            return FinalDecision(
                primary_conclusion=best,
                conflicts=conflicts,
                explanation=explanation,
                ruling_basis="uncertainty",
                suppressed_views=suppressed,
                system_state=system_state,
                counterfactual_thresholds=counterfactuals,
                robustness_warning=robustness_warning
            )
        
        # RULE 4: Consequence-weighted scoring (default path)
        scores = []
        for c in conclusions:
            weight = self.config.weights.get(c.time_scale, 1.0)
            loss = self.LOSS_MULTIPLIERS.get(c.time_scale, 1.0)
            urgency = self.URGENCY_BOOST.get(c.sentiment, 1.0)
            
            # Apply structural legitimacy penalty to Long-term
            if c.time_scale == "Long":
                weight *= self.structural_legitimacy
            
            # Final score: confidence × weight × loss × urgency
            score = c.confidence * weight * loss * urgency
            scores.append((score, c, weight, loss, urgency))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        winner_score, winner, w_weight, w_loss, w_urgency = scores[0]
        
        # Build explicit explanation with consequence awareness
        score_breakdown = " | ".join([
            f"{c.time_scale}({c.sentiment.value}): {c.confidence:.0%}×{w:.1f}×{l:.1f}×{u:.1f} = {s:.2f}"
            for s, c, w, l, u in scores
        ])
        
        explanation = f"CONSEQUENCE-WEIGHTED: {winner.time_scale} wins (score {winner_score:.2f}). {score_breakdown}"
        
        # Robustness assessment
        score_gap = winner_score - scores[1][0] if len(scores) > 1 else winner_score
        if score_gap < 0.5:
            robustness_warning = "Rational under scoring model. Robustness: LOW (narrow margin, sensitive to parameter changes)"
        elif len(conflicts) > 3:
            robustness_warning = "Rational under scoring model. Robustness: UNCERTAIN (high conflict count suggests model stress)"
        else:
            robustness_warning = "Rational under scoring model. Robustness: MODERATE (clear winner, but model-dependent)"
        
        # Generate counterfactuals for each suppressed view
        for score, c, w, l, u in scores[1:]:
            needed_confidence = (winner_score / (w * l * u)) if (w * l * u) > 0 else 1.0
            needed_confidence = min(needed_confidence, 1.0)
            
            counterfactuals.append(
                f"{c.time_scale} needs {needed_confidence:.0%} confidence (has {c.confidence:.0%}) to flip"
            )
            
            confidence_gap = winner.confidence - c.confidence
            if confidence_gap > 0.2:
                reason = f"{c.sentiment.value} dismissed - {confidence_gap:.0%} confidence deficit"
            else:
                reason = f"{c.sentiment.value} overruled by consequence weighting"
            suppressed.append((c.time_scale, reason))
        
        # System state taxonomy
        has_danger_signal = any(
            c.sentiment in {Sentiment.CRASH, Sentiment.SPIKE, Sentiment.OVEREXTENDED_HIGH, Sentiment.OVEREXTENDED_LOW}
            for c in conclusions
        )
        high_severity_conflicts = [c for c in conflicts if c.severity > 0.7]
        
        # State determination logic
        if len(high_severity_conflicts) > 3 or (has_danger_signal and len(suppressed) > 1):
            system_state = "PRECARIOUS"
        elif len(conflicts) > 5 or self.structural_legitimacy < 0.7:
            system_state = "FRAGILE"
        elif len(conflicts) > 2:
            system_state = "CONTESTED"
        elif len(conflicts) > 0:
            system_state = "STABLE"  # Conflicts exist but low severity
        else:
            system_state = "STABLE"
        
        return FinalDecision(
            primary_conclusion=winner,
            conflicts=conflicts,
            explanation=explanation,
            ruling_basis="consequence_weighted",
            suppressed_views=suppressed,
            system_state=system_state,
            counterfactual_thresholds=counterfactuals,
            robustness_warning=robustness_warning
        )
