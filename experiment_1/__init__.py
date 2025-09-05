from otree.api import *
import random

doc = """
Investment Game - Supply Chain Resilience
"""

class C(BaseConstants):
    NAME_IN_URL = 'otree_nd'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 10
    INITIAL_PROFIT = 10000  # C₀ (100 rounds)
    DISRUPTION_COST = 2000  # C_I (baseline disruption impact)
    BASIC_PROBABILITY = 5   # p₀ (baseline probability)

class Subsession(BaseSubsession):
    pass

class Group(BaseGroup):
    pass

class Player(BasePlayer):
    money_input = models.IntegerField(
        min=0,
        max=100,
        label="Spending Amount",
        blank=False,
    )
    is_disrupted = models.BooleanField(
        initial=False
    )
    cost_of_disruption = models.IntegerField(
        initial=0,
    )
    total_costs = models.IntegerField(
        initial=0,
    )
    expected_profit = models.IntegerField(
        initial=C.INITIAL_PROFIT,
    )
    round_calculated = models.BooleanField(initial=False)

class CombinedResult(ExtraModel):
    player = models.Link(Player)
    spending = models.IntegerField()
    is_disrupted = models.BooleanField()
    cost_of_disruption = models.IntegerField()
    total_costs = models.IntegerField(initial=0)
    expected_profit = models.IntegerField(initial=C.INITIAL_PROFIT)

# PAGES
class LandingPage(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

class GamePage(Page):
    form_model = 'player'
    form_fields = ['money_input']
    
    @staticmethod
    def vars_for_template(player: Player):
        all_players = player.in_all_rounds()
        results = []
        for p in all_players[:player.round_number]:
            player_results = CombinedResult.filter(player=p)
            results.extend(player_results)
        
        results = sorted(results, key=lambda x: x.player.round_number, reverse=True)
        
        current_round_result = None
        if player.round_calculated:
            current_results = CombinedResult.filter(player=player)
            if current_results:
                current_round_result = current_results[0]
        
        last_result = results[0] if results else None
        
        avg_cost = 0
        if results:
            total_costs_sum = sum(r.total_costs for r in results)
            avg_cost = total_costs_sum // len(results)
        
        current_profit = last_result.expected_profit if last_result else C.INITIAL_PROFIT
        
        game_completed = (player.round_number == C.NUM_ROUNDS and 
                         len(CombinedResult.filter(player=player)) > 0)
        
        final_stats = None
        if game_completed:
            total_investment = sum(r.investment for r in results)
            total_disruption_cost = sum(r.cost_of_disruption for r in results)
            final_profit = results[0].expected_profit if results else C.INITIAL_PROFIT
            
            final_stats = {
                'total_investment': total_investment,
                'total_disruption_cost': total_disruption_cost,
                'final_profit': final_profit,
                'initial_profit': C.INITIAL_PROFIT,
                'all_results': results,
            }
        num_rounds_plus_one = player.round_number + 1
        num_rounds_minus_one = player.round_number - 1
        
        return dict(
            combined_result=results,
            current_round_result=current_round_result,
            last_result=last_result,
            average_cost=avg_cost,
            initial_profit=C.INITIAL_PROFIT,
            current_profit=current_profit,
            is_final_round=player.round_number == C.NUM_ROUNDS,
            game_completed=game_completed,
            final_stats=final_stats,
            round_calculated=player.round_calculated,
            num_rounds_plus_one=num_rounds_plus_one,
            num_rounds_minus_one=num_rounds_minus_one,
        )
    
    @staticmethod
    def live_method(player: Player, data):
        if data['action'] == 'calculate_result':
            investment = data['investment']
            
            if investment < 0 or investment > 100:
                return {'status': 'error', 'message': 'Investment must be between 0 and 100'}
            
            player.money_input = investment
            
            # CORRECTED LOGIC: Following the mathematical formulas
            # p(x) = p₀ - p₀ * (x/100) = 5 - 5 * (x/100) = 5 * (1 - x/100)
            disruption_probability = C.BASIC_PROBABILITY * (1 - investment / 100)
            
            # C_I(x) = C_I - C_I * (x/100) = C_I * (1 - x/100)
            disruption_impact = C.DISRUPTION_COST * (1 - investment / 100)
            
            # Generate random number (0-100) to check for disruption
            random_number = random.uniform(0, 100)
            
            if random_number < disruption_probability:
                # Disruption occurs
                player.is_disrupted = True
                player.cost_of_disruption = disruption_impact
            else:
                # No disruption
                player.is_disrupted = False
                player.cost_of_disruption = 0
            
            # Calculate profit: Π(x) = C₀ - x - p(x) * C_I(x)
            # But since we already determined if disruption occurred, we use actual cost
            if player.round_number > 1:
                # Get previous round's profit
                prev_player = player.in_round(player.round_number - 1)
                prev_results = CombinedResult.filter(player=prev_player)
                if prev_results:
                    prev_expected_profit = prev_results[0].expected_profit
                    prev_total_costs = prev_results[0].total_costs
                else:
                    prev_expected_profit = C.INITIAL_PROFIT
                    prev_total_costs = 0
                
                # Calculate new profit based on previous round
                player.expected_profit = prev_expected_profit - investment - player.cost_of_disruption
                player.total_costs = prev_total_costs + investment + player.cost_of_disruption
            else:
                # First round - calculate from initial profit
                player.expected_profit = C.INITIAL_PROFIT - investment - player.cost_of_disruption
                player.total_costs = investment + player.cost_of_disruption
            
            # Delete existing result for this round if any
            existing_results = CombinedResult.filter(player=player)
            for result in existing_results:
                result.delete()
            
            # Create the combined result record
            CombinedResult.create(
                player=player,
                investment=investment,
                is_disrupted=player.is_disrupted,
                cost_of_disruption=player.cost_of_disruption,
                total_costs=player.total_costs,
                expected_profit=player.expected_profit,
            )
            
            player.round_calculated = True
            
            return {
                'status': 'success',
                'result': {
                    'round': player.round_number,
                    'investment': investment,
                    'is_disrupted': player.is_disrupted,
                    'disruption_probability': round(disruption_probability, 2),
                    'disruption_impact_if_occurs': disruption_impact,
                    'cost_of_disruption': player.cost_of_disruption,
                    'total_costs': player.total_costs,
                    'expected_profit': player.expected_profit,
                }
            }
        
        elif data['action'] == 'next_round':
            player.round_calculated = False
            return {'status': 'next_round'}
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Fallback calculation if live_method wasn't used
        if not player.round_calculated and player.money_input is not None:
            investment = player.money_input
            
            # CORRECTED LOGIC: Following the mathematical formulas
            disruption_probability = C.BASIC_PROBABILITY * (1 - investment / 100)
            disruption_probability = max(0, disruption_probability)
            
            disruption_impact = C.DISRUPTION_COST * (1 - investment / 100)
            disruption_impact = max(0, int(disruption_impact))
            
            random_number = random.uniform(0, 100)
            
            if random_number < disruption_probability:
                player.is_disrupted = True
                player.cost_of_disruption = disruption_impact
            else:
                player.is_disrupted = False
                player.cost_of_disruption = 0
            
            if player.round_number > 1:
                prev_player = player.in_round(player.round_number - 1)
                prev_results = CombinedResult.filter(player=prev_player)
                if prev_results:
                    prev_expected_profit = prev_results[0].expected_profit
                    prev_total_costs = prev_results[0].total_costs
                else:
                    prev_expected_profit = C.INITIAL_PROFIT
                    prev_total_costs = 0
                
                player.expected_profit = prev_expected_profit - investment - player.cost_of_disruption
                player.total_costs = prev_total_costs + investment + player.cost_of_disruption
            else:
                player.expected_profit = C.INITIAL_PROFIT - investment - player.cost_of_disruption
                player.total_costs = investment + player.cost_of_disruption
            
            existing_results = CombinedResult.filter(player=player)
            for result in existing_results:
                result.delete()
            
            CombinedResult.create(
                player=player,
                investment=investment,
                is_disrupted=player.is_disrupted,
                cost_of_disruption=player.cost_of_disruption,
                total_costs=player.total_costs,
                expected_profit=player.expected_profit,
            )


class Results(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Lấy số trang từ query parameter
        page = player.participant.vars.get('page', 1)
        try:
            page = int(page)
            if page < 1:
                page = 1
        except (TypeError, ValueError):
            page = 1
        player.participant.vars['current_page'] = page

    @staticmethod
    def vars_for_template(player: Player):
        all_players = player.in_all_rounds()
        all_results = []
        for p in all_players:
            player_results = CombinedResult.filter(player=p)
            all_results.extend(player_results)

        all_results = sorted(all_results, key=lambda x: x.player.round_number)
        
        total_investment = sum(r.investment for r in all_results)
        total_disruption_cost = sum(r.cost_of_disruption for r in all_results)
        final_profit = all_results[-1].expected_profit if all_results else C.INITIAL_PROFIT
        average_investment = total_investment // C.NUM_ROUNDS if all_results else 0
        num_disruptions = sum(1 for r in all_results if r.is_disrupted)
        profit_change = final_profit - C.INITIAL_PROFIT
        
        return dict(
            all_results=all_results,
            total_results=len(all_results),
            total_investment=total_investment,
            total_disruption_cost=total_disruption_cost,
            final_profit=final_profit,
            initial_profit=C.INITIAL_PROFIT,
            average_investment=average_investment,
            num_disruptions=num_disruptions,
            profit_change=profit_change,
        )
    
page_sequence = [LandingPage, GamePage, Results]