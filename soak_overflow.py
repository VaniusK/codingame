import sys
import math
from abc import ABC, abstractmethod
import random
import time
from collections import deque

random.seed(42)

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


    def __add__(self, other):
        if isinstance(other, Point):
            return Point(self.x + other.x, self.y + other.y)
        if isinstance(other, tuple):
            return Point(self.x + other[0], self.y + other[1])

    def __sub__(self, other):
        return abs(self.x - other.x) + abs(self.y - other.y)

    def __eq__(self, other):
        if isinstance(other, Point):
            return self.x == other.x and self.y == other.y
        return False

    def __str__(self):
        return f"(X:{self.x}; Y:{self.y})"

    def __repr__(self):
        return f"(X:{self.x}; Y:{self.y})"

    def copy(self):
        return Point(self.x, self.y)

def MOVE(point: Point) -> str:
    return f"MOVE {point.x} {point.y}"

def SHOOT(agent) -> str:
    return f"SHOOT {agent.id}"

def THROW(point: Point) -> str:
    return f"THROW {point.x} {point.y}"

def HUNKER_DOWN() -> str:
    return "HUNKER_DOWN"

def MESSAGE(text: str) -> str:
    return f"MESSAGE {text}"

COVER_DEFENCE_VALUES = [0, 0.5, 0.75]
BOMB_DAMAGE = 30
BOMB_USAGE_PENALTY = -0.7
THROW_GLANCING_HIT_PENALTY = 0.35  # Enemy may dodge
THROW_FRIENDLY_FIRE_PENALTY = -2
THROW_LOW_HP_BONUS = 0

STAY_AWAY_DISTANCE = 2

THROW_DISTANCE = 4


def is_covered(position: Point, enemy_position, cover_position, direction) -> bool:
    if enemy_position - position <= enemy_position - (position + direction + direction):
        # Agent and enemy must be on opposite sides of the cover
        return False
    if enemy_position - cover_position == 1:
        # Enemy must not be adjacent to the cover
        return False
    return True

class GameMap:
    def __init__(self, height, width):
        self.height = height
        self.width = width
        self.tiles = [[-1 for _ in range(width)] for _ in range(height)]

    def __getitem__(self, index) -> int:
        row: int = -1
        col: int = -1
        if isinstance(index, tuple):
            row, col = index
        if isinstance(index, Point):
            row = index.y
            col = index.x
        return self.tiles[row][col]

    def __setitem__(self, index, value: int):
        row: int = -1
        col: int = -1
        if isinstance(index, tuple):
            row, col = index
        if isinstance(index, Point):
            row = index.y
            col = index.x
        self.tiles[row][col] = value

    def is_within(self, point: Point) -> bool:
        return 0 <= point.x < self.width and 0 <= point.y < self.height

class Agent:
    def __init__(self, id, player, shoot_cooldown, optimal_range, soaking_power, splash_bombs):
        self.id = id
        self.player = player
        self.shoot_cooldown = shoot_cooldown
        self.optimal_range = optimal_range
        self.soaking_power = soaking_power
        self.splash_bombs = splash_bombs
        self.cooldown = -1
        self.wetness = -1
        self.position = Point(-1, -1)
        self.spawn_position = None
        self.desired_position = None
        self._role = None
        self.push_target = None
        self.selected_phrase_index = -1

    def act(self, commands):
        args = [str(self.id)] + [command[0](*command[1:]) for command in commands if command is not None]
        line = ";".join(args)
        print(line)

    @property
    def role(self):
        return self._role

    @role.setter
    def role(self, value):
        if value != self._role:
            self._role = value
            self.selected_phrase_index = -1


class GameState:
    def __init__(self, my_id):
        self.my_id = my_id
        self.turn = 0
        self.game_map: GameMap = GameMap(0, 0)
        self.agents: dict[int, Agent] = {}
        self.my_agents: list[Agent] = []
        self.enemy_agents: list[Agent] = []
        self.influence = 0
        self.stepped = []
        self.thrown_bombs = []

    def read_initial_input(self):
        agent_count = int(input())
        for i in range(agent_count):
            agent_id, player, shoot_cooldown, optimal_range, soaking_power, splash_bombs = [int(j) for j in
                                                                                            input().split()]
            self.agents[agent_id] = Agent(agent_id, player, shoot_cooldown, optimal_range, soaking_power, splash_bombs)

        width, height = [int(i) for i in input().split()]
        self.game_map = GameMap(height, width)
        self.stepped = [[0 for _ in range(self.game_map.width)] for _ in range(self.game_map.height)]
        for i in range(height):
            inputs = input().split()
            for j in range(width):
                self.game_map.tiles[i][j] = int(inputs[3 * j + 2])


    def update_turn_input(self):
        self.turn += 1
        self.my_agents = []
        self.enemy_agents = []
        self.thrown_bombs = []

        agent_count = int(input())
        alive_agents_ids = set()
        for i in range(agent_count):
            agent_id, x, y, cooldown, splash_bombs, wetness = [int(j) for j in input().split()]
            agent = self.agents[agent_id]
            agent.position = Point(x, y)
            self.stepped[y][x] += 1
            agent.cooldown = cooldown
            agent.wetness = wetness
            agent.splash_bombs = splash_bombs
            if not agent.spawn_position:
                agent.spawn_position = Point(x, y)
            agent.desired_position = None
            alive_agents_ids.add(agent_id)

        for agent_id in alive_agents_ids:
            agent = self.agents[agent_id]
            if agent.player == self.my_id:
                self.my_agents.append(agent)
            else:
                self.enemy_agents.append(agent)

        temp = list(self.agents.values())
        for agent in temp:
            if agent.id not in alive_agents_ids:
                self.agents.pop(agent.id)

        self.update_influence()
        self.update_roles()

        my_agent_count = int(input())
        assert my_agent_count == len(self.my_agents)

    def update_roles(self):
        for agent in self.my_agents:
            if agent.soaking_power == 16:
                agent.role = "Heavy"
            if agent.optimal_range == 6:
                agent.role = "Sniper"
            if agent.soaking_power == 32 and agent.optimal_range == 2:
                agent.role = "Heavy"  # Pyro
            if agent.soaking_power == 8:
                agent.role = "Scout"  # Scout



    def update_influence(self):
        self.influence = 0
        for y in range(self.game_map.height):
            for x in range(self.game_map.width):
                position = Point(x, y)
                closest_my_agent = 1e18
                for agent in self.my_agents:
                    if agent.wetness < 50:
                        closest_my_agent = min(closest_my_agent, agent.position - position)
                    else:
                        closest_my_agent = min(closest_my_agent, (agent.position - position) * 2)

                closest_enemy_agent = 1e18
                for agent in self.enemy_agents:
                    if agent.wetness < 50:
                        closest_enemy_agent = min(closest_enemy_agent, agent.position - position)
                    else:
                        closest_enemy_agent = min(closest_enemy_agent, (agent.position - position) * 2)

                if closest_my_agent < closest_enemy_agent:
                    self.influence += 1
                if closest_my_agent > closest_enemy_agent:
                    self.influence -= 1


def calculate_agent_value(game_state: GameState, agent: Agent) -> float:
    value = agent.soaking_power / (agent.shoot_cooldown + 1) * (agent.optimal_range ** (1/3)) * (1 if agent.wetness < 50 else 1)
    return value


class Strategy(ABC):
    phrases = []
    name = ""

    def calculate_damage(self, game_state: GameState, agent: Agent, target_position: Point, extra_protection, ignore_cover=False):
        distance = target_position - agent.position
        basic_damage: float = 0
        if distance <= agent.optimal_range:
            basic_damage = agent.soaking_power
        elif distance <= agent.optimal_range * 2:
            basic_damage = agent.soaking_power / 2
        directions = [(-1, 0), (1, 0), (0, 1), (0, -1)]
        protection = 0
        for direction in directions:
            cover_position: Point = target_position + direction
            if not game_state.game_map.is_within(cover_position):
                continue
            cover_value = COVER_DEFENCE_VALUES[game_state.game_map[cover_position]]
            if game_state.game_map.is_within(cover_position):
                if not ignore_cover and is_covered(target_position, agent.position, cover_position, direction):
                    protection = max(protection, cover_value)

        damage = basic_damage * (1 - protection - extra_protection)
        return damage

    def calculate_recieved_damage_if_targeted(self, game_state: GameState, position: Point, extra_protection=0):
        damage = 0
        for enemy in game_state.enemy_agents:
            damage += self.calculate_damage(game_state, enemy, position, extra_protection)
        return damage

    def is_point_occupied(self, game_state: GameState, point: Point):
        for agent in game_state.agents.values():
            if agent.position == point:
                return True
            if agent.desired_position == point:
                return True
        return False

    def get_possible_throw_positions(self, game_state: GameState, agent : Agent):
        possible_throw_positions = []
        for y in range(game_state.game_map.height):
            for x in range(game_state.game_map.width):
                throw_position = Point(x, y)
                if throw_position - agent.position <= THROW_DISTANCE:
                    weight = 0
                    weight += BOMB_DAMAGE * BOMB_USAGE_PENALTY
                    for affected_agent in game_state.agents.values():
                        if abs(affected_agent.position.x - throw_position.x) <= 1 and abs(
                                affected_agent.position.y - throw_position.y) <= 1:
                            dealt_damage = BOMB_DAMAGE
                            coeff = 1
                            coeff *= (1 - THROW_GLANCING_HIT_PENALTY * (affected_agent.position - throw_position))
                            if affected_agent.player == agent.player:
                                coeff *= THROW_FRIENDLY_FIRE_PENALTY
                            if affected_agent.wetness < 100:
                                coeff *= (1 + THROW_LOW_HP_BONUS / (100 - affected_agent.wetness))

                            weight += coeff * dealt_damage

                            coeff *= calculate_agent_value(game_state, affected_agent)
                            if agent.id == 6:
                                print(affected_agent.id, coeff, dealt_damage, file=sys.stderr)
                    possible_throw_positions.append((weight, throw_position))

        possible_throw_positions.sort(key=lambda x: -x[0])
        return possible_throw_positions

    def simulate_throw(self, game_state: GameState, throw_position: Point):
        game_state.thrown_bombs.append(throw_position)
        for affected_agent in game_state.agents.values():
            if abs(affected_agent.position.x - throw_position.x) <= 1 and abs(
                    affected_agent.position.y - throw_position.y) <= 1:
                affected_agent.wetness += 30

    def simulate_shot(self, game_state: GameState, agent: Agent, victim: Agent):
        damage = self.calculate_damage(game_state, agent, victim.position, 0.25)
        victim.wetness += damage

    def simulate_move(self, game_state : GameState, agent: Agent, position: Point):
        if position is None:
            return
        assert agent.position - position == 1
        agent.position = position

    def get_covers(self, game_state: GameState):
        covers = []
        for y in range(game_state.game_map.height):
            for x in range(game_state.game_map.width):
                if game_state.game_map[y, x] > 0:
                    covers.append(Point(x, y))
        return covers

    def get_best_enemy_to_attack(self, game_state: GameState, agent: Agent):
        def comp(enemy):
            if enemy.wetness >= 100:
                return 0
            damage = self.calculate_damage(game_state, agent, enemy.position, 0.25, False)
            shots_to_kill = 1000000
            if damage > 0:
                shots_to_kill = (100 - enemy.wetness + damage - 1) // damage
            value = calculate_agent_value(game_state, enemy)
            return value / shots_to_kill

        best_enemy = sorted(game_state.enemy_agents, key=comp)[-1]

        return best_enemy

    def get_best_cover_target(self, game_state, agent: Agent):
        possible_covers: list = []
        agent.desired_position = None
        if agent.spawn_position.x == 0:
            possible_covers = [i + (-1, 0) for i in self.get_covers(game_state) if game_state.game_map[i + (-1, 0)] == 0]
            possible_covers = [i for i in possible_covers if i.x <= game_state.game_map.width // 2]
        else:
            possible_covers = [i + (1, 0) for i in self.get_covers(game_state) if game_state.game_map[i + (1, 0)] == 0]
            possible_covers = [i for i in possible_covers if i.x >= game_state.game_map.width // 2]
        middle = Point(game_state.game_map.width // 2, game_state.game_map.height // 2)
        possible_covers.sort(key=lambda position: position - middle)
        return possible_covers[0] if possible_covers else None

    def get_next_path_position(self, game_state: GameState, start_position: Point, end_position: Point, target_agent: Agent, STAY_AWAY_RANGE):
        width = game_state.game_map.width
        height = game_state.game_map.height
        priority_map = [[0 for _ in range(width)] for _ in range(height)]
        previous_step = [[Point(-1, -1) for _ in range(width)] for _ in range(height)]
        for y in range(height):
            for x in range(width):
                if game_state.game_map[y, x] > 0:
                    priority_map[y][x] = 29

        for agent in game_state.agents.values():
            if agent.id == target_agent.id:
                continue
            for x2 in range(agent.position.x - STAY_AWAY_RANGE, agent.position.x + STAY_AWAY_RANGE + 1):
                for y2 in range(agent.position.y - STAY_AWAY_RANGE, agent.position.y + STAY_AWAY_RANGE + 1):
                    position = Point(x2, y2)
                    if game_state.game_map.is_within(position):
                        if agent.player == target_agent.player:
                            if agent.id != target_agent.id:
                                if position == agent.position and position - start_position <= 1:
                                    priority_map[y2][x2] = 29
                                if STAY_AWAY_RANGE != 0:
                                    priority_map[y2][x2] += STAY_AWAY_RANGE * 2 + 1 - (position - agent.position)
                                    priority_map[y2][x2] = min(priority_map[y2][x2], 29)

        for bomb in game_state.thrown_bombs:
            for x2 in range(bomb.x - 1, bomb.x + 2):
                for y2 in range(bomb.y - 1, bomb.y + 2):
                    position = Point(x2, y2)
                    if game_state.game_map.is_within(position):
                        priority_map[y2][x2] = 29

        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        q = [deque() for _ in range(30)]
        q[priority_map[start_position.y][start_position.x]].append(start_position)
        steps = 1
        while sum([len(i) for i in q]) > 0:
            i = 0
            while i < 30:
                flag = False
                if len(q[i]) > 0:
                    now = q[i].popleft()
                    if now != start_position and priority_map[start_position.y][start_position.x] > 0:
                        return now

                    for direction in directions:
                        now2 = now + direction
                        if not game_state.game_map.is_within(now2):
                            continue


                        if priority_map[now2.y][now2.x] != 29 and previous_step[now2.y][now2.x].x == -1:
                            q[priority_map[now2.y][now2.x]].append(now2)
                            previous_step[now2.y][now2.x] = now
                            flag = True
                            steps += 1

                if flag:
                    break
                i += 1


        now = start_position
        for y in range(height):
            for x in range(width):
                if previous_step[y][x].x != -1:
                    if now == start_position or (now - end_position) > (Point(x, y) - end_position):
                        now = Point(x, y)

        while True:
            if now == Point(-1, -1):
                return None
            if previous_step[now.y][now.x] == start_position:
                return now
            now = previous_step[now.y][now.x]

    def should_stay_away(self, game_state: GameState, agent: Agent):
        for enemy in game_state.enemy_agents:
            if enemy.position - agent.position <= THROW_DISTANCE + 4 and enemy.splash_bombs > 0:
                return True
        return False

    def has_enemy_to_attack(self, game_state: GameState, agent: Agent):
        for enemy in game_state.enemy_agents:
            if self.calculate_damage(game_state, agent, enemy.position, 0) == agent.soaking_power:
                return True
        return False

    def get_message_action(self, agent: Agent):
        if agent.selected_phrase_index == -1 or random.randint(1, 10) <= 1 or agent.selected_phrase_index >= len(self.phrases):
            agent.selected_phrase_index = random.randint(0, len(self.phrases) - 1)
        return (MESSAGE, self.name + ": " + self.phrases[agent.selected_phrase_index])

    @abstractmethod
    def get_move_action(self, game_state: GameState, agent: Agent):
        pass

    @abstractmethod
    def get_attack_action(self, game_state: GameState, agent: Agent):
        pass

    def get_actions_for_agent(self, game_state: GameState, agent: Agent):
        actions = [None, None, None]

        move_action = self.get_move_action(game_state, agent)
        if move_action:
            if move_action[1]:
                actions[0] = move_action
                self.simulate_move(game_state, agent, move_action[1])

        attack_action = self.get_attack_action(game_state, agent)
        if attack_action:
            if len(attack_action) == 1 or attack_action[1]:
                if attack_action[0] == THROW:
                    self.simulate_throw(game_state, attack_action[1])
                if attack_action[0] == SHOOT:
                    self.simulate_shot(game_state, agent, attack_action[1])
                actions[1] = attack_action

        message_action = self.get_message_action(agent)
        actions[2] = message_action

        return actions


class SniperStrategy(Strategy):
    """
    High range and damage but horrible shooting speed, leading to mediocre DPS.
    Needs a cover to survive so he finds one closer to the middle and sits there.
    """
    phrases = ["That one's for me, boys!", "That's how we do it in the bush!", "Sniping's a good job, mate!", "Right, then!", "Yeah, that seems about right!", "No worries!", "Aces.", "All in a days work.", "I told ya sniping was a good job!", "Well I'll be stuffed!", "I make it look easy.", "Now that is how it's done!", "I could do this all day.", "Ahh, that's apples mate."]
    name = "Sniper"

    def get_move_action(self, game_state: GameState, agent: Agent):
        if "Scout" in [agent.role for agent in
                       game_state.my_agents] and abs(agent.position.x - agent.spawn_position.x) > game_state.game_map.width // 3:
            return None
        cover_target = self.get_best_cover_target(game_state, agent)
        if cover_target and cover_target != agent.position:
            agent.desired_position = cover_target.copy()
            should_stay_away = self.should_stay_away(game_state, agent)
            cover_target = self.get_next_path_position(game_state, agent.position, cover_target, agent, 0)
            return (MOVE, cover_target)
        return None

    def get_attack_action(self, game_state: GameState, agent: Agent):
        throw_locations = self.get_possible_throw_positions(game_state, agent)
        throw_choice = (-1, None)
        if throw_locations and agent.splash_bombs > 0:
            throw_choice = throw_locations[0]
        enemy_to_attack = self.get_best_enemy_to_attack(game_state, agent)
        shoot_choice = (self.calculate_damage(game_state, agent, enemy_to_attack.position, 0.25), enemy_to_attack)
        if agent.cooldown != 0:
            shoot_choice = (-1, enemy_to_attack)
        if shoot_choice[0] > throw_choice[0] and shoot_choice[0] > 0:
            return (SHOOT, shoot_choice[1])
        elif throw_choice[0] > 0:
            return (THROW, throw_choice[1])
        return tuple([HUNKER_DOWN])


class HeavyStrategy(Strategy):
    """
    Good DPS, average range.
    Infantry, main firepower and border pushers.
    """
    phrases = ["Look at me! Look at me!", "I am hero!", "It is good day to be Giant Man!", "Everyone! Look at me!", "Yes!", "Very good!", "Very good, very VERY good!", "I am most dangerous man, in history of WORLD!", "Who dares stand against me NOW?", "Fear me, cowards!", "I am credit to team.", "The medal - it is so tiny!", "I have many medals!", "Another medal! Is good!", "I am big war hero!", "Now I am king of team!"]
    name = "Heavy"

    def get_move_action(self, game_state: GameState, agent: Agent):
        if "Scout" in [agent.role for agent in game_state.my_agents] and abs(agent.position.x - agent.spawn_position.x) > game_state.game_map.width // 3:
            return None
        if self.calculate_recieved_damage_if_targeted(game_state, agent.position, 0.25) == 0 and (agent.wetness > 75 or (game_state.influence > 0 and agent.position.x - agent.spawn_position.x >= game_state.game_map.width // 2)):
            return None
        else:
            backmost_enemy = sorted(game_state.enemy_agents, key=lambda enemy: abs(enemy.position.x - agent.spawn_position.x))[-1]
            push_target = backmost_enemy.position.copy()
            if agent.spawn_position.x == 0:
                push_target += (1, 0)
            else:
                push_target += (-1, 0)
            if push_target and push_target != agent.position:
                agent.desired_position = push_target.copy()
                should_stay_away = self.should_stay_away(game_state, agent)
                push_target = self.get_next_path_position(game_state, agent.position, push_target, agent, STAY_AWAY_DISTANCE if should_stay_away else 0)
                if self.has_enemy_to_attack(game_state, agent) and self.calculate_recieved_damage_if_targeted(game_state, agent.position, 0.25) < self.calculate_recieved_damage_if_targeted(game_state, push_target, 0.25):
                    return None
                return (MOVE, push_target)
        return None

    def get_attack_action(self, game_state: GameState, agent: Agent):
        if agent.wetness >= 75 and self.calculate_recieved_damage_if_targeted(game_state, agent.position, 0.25) == 0:
            return tuple([HUNKER_DOWN])
        throw_locations = self.get_possible_throw_positions(game_state, agent)
        throw_choice = (-1, None)
        if throw_locations and agent.splash_bombs > 0:
            throw_choice = throw_locations[0]
        enemy_to_attack = self.get_best_enemy_to_attack(game_state, agent)
        shoot_choice = (self.calculate_damage(game_state, agent, enemy_to_attack.position, 0.25), enemy_to_attack)
        if agent.cooldown != 0:
            shoot_choice = (-1, enemy_to_attack)
        if shoot_choice[0] > throw_choice[0] and shoot_choice[0] > 0:
            return (SHOOT, shoot_choice[1])
        elif throw_choice[0] > 0:
            return (THROW, throw_choice[1])
        return tuple([HUNKER_DOWN])

class ScoutStrategy(Strategy):
    """
    Low DPS, low range.
    Almost useless in a fight so he tries to sneak behind enemy forces to gain some of their territory.
    (if he survives, as his prime role is being a cannon fodder for bombs)
    """
    phrases = ["HUG!!!", "Hey, look at me, look at me!", "Hey, look at me, Ma!", "Aw, fellas!", "Hi, Ma!", "Look at me!", "No otha' class gonna do dat!", "You see dat?", "You seein' dis?", "I'll put it in my trophy room, with the othas.", "I don't know who to thank first... Oh, I know, me!", "Bang! I make it look easy."]
    name = "Scout"

    def get_move_action(self, game_state: GameState, agent: Agent):
        enemy_with_most_bombs = sorted(game_state.enemy_agents, key=lambda enemy: enemy.splash_bombs)[-1]
        desired_position = Point(0, 0)
        middle = Point(game_state.game_map.width // 2, game_state.game_map.height // 2)
        if agent.splash_bombs > 0:
            strongest_enemy = sorted(game_state.enemy_agents, key=lambda enemy: calculate_agent_value(game_state, enemy))[-1]
            desired_position = strongest_enemy.position
            if strongest_enemy.position - agent.position <= 2:
                return None
        elif enemy_with_most_bombs.splash_bombs > 0:
            agent.selected_phrase_index = 0
            enemy_closest_to_middle = sorted(game_state.enemy_agents, key=lambda enemy: enemy.position - middle)[0]
            desired_position = enemy_closest_to_middle.position
        else:
            if agent.spawn_position.x == 0:
                desired_position = Point(game_state.game_map.width - 1, agent.position.y)
            else:
                desired_position = Point(0, agent.position.y)
        should_stay_away = self.should_stay_away(game_state, agent)
        desired_position = self.get_next_path_position(game_state, agent.position, desired_position, agent, 0)
        return (MOVE, desired_position)

    def get_attack_action(self, game_state: GameState, agent: Agent):
        throw_locations = self.get_possible_throw_positions(game_state, agent)
        print(throw_locations, file=sys.stderr)
        throw_choice = (-1, None)
        if throw_locations and agent.splash_bombs > 0:
            throw_choice = throw_locations[0]
        enemy_to_attack = self.get_best_enemy_to_attack(game_state, agent)
        shoot_choice = (self.calculate_damage(game_state, agent, enemy_to_attack.position, 0.25), enemy_to_attack)
        if agent.cooldown != 0:
            shoot_choice = (-1, enemy_to_attack)
        if shoot_choice[0] > throw_choice[0] and shoot_choice[0] > 0:
            return (SHOOT, shoot_choice[1])
        elif throw_choice[0] > 0:
            return (THROW, throw_choice[1])
        return tuple([HUNKER_DOWN])

class DemomanStrategy(Strategy):
    """
    Subclass, used until agent has no bombs.
    """
    phrases = ["Aye, that's the way ye do it! Hehah!", "Time to get bluttered!", "Guts and glory, lads!", "Aye, that's the way ye do it! Hehah!", "Time to get bluttered!", "That'll teach 'em!", "Stand on the bloody point, ya half-wit!", "Stand on the point, ya git!"]
    name = "Demoman"

    def get_move_action(self, game_state: GameState, agent: Agent):
        closest_enemy = sorted(game_state.enemy_agents, key=lambda enemy: enemy.position - agent.position)[0]
        if closest_enemy.position - agent.position <= THROW_DISTANCE:
            return None
        enemy_with_most_bombs = sorted(game_state.enemy_agents, key=lambda enemy: enemy.splash_bombs)[-1]
        desired_position = enemy_with_most_bombs.position
        should_stay_away = self.should_stay_away(game_state, agent)
        target = self.get_next_path_position(game_state, agent.position, desired_position, agent, STAY_AWAY_DISTANCE if should_stay_away else 0)
        return (MOVE, target)

    def get_attack_action(self, game_state: GameState, agent: Agent):
        throw_locations = self.get_possible_throw_positions(game_state, agent)
        throw_choice = (-1, None)
        if throw_locations and agent.splash_bombs > 0:
            throw_choice = throw_locations[0]
        enemy_to_attack = self.get_best_enemy_to_attack(game_state, agent)
        shoot_choice = (self.calculate_damage(game_state, agent, enemy_to_attack.position, 0.25), enemy_to_attack)
        if agent.cooldown != 0:
            shoot_choice = (-1, enemy_to_attack)
        if shoot_choice[0] > throw_choice[0] and shoot_choice[0] > 0:
            return (SHOOT, shoot_choice[1])
        elif throw_choice[0] > 0:
            return (THROW, throw_choice[1])
        return tuple([HUNKER_DOWN])


def choose_strategy(game_state: GameState, agent: Agent):
    if agent.role == "Heavy":
        return HeavyStrategy
    if agent.role == "Sniper":
        return SniperStrategy
    if agent.role == "Scout":
        return ScoutStrategy


my_id = int(input())
game_state = GameState(my_id)
game_state.read_initial_input()

while True:
    game_state.update_turn_input()

    for agent in game_state.my_agents:
        start = time.time()
        strategy = choose_strategy(game_state, agent)()
        actions = strategy.get_actions_for_agent(game_state, agent)
        #print(time.time() - start, file=sys.stderr)
        agent.act(actions)

'''

TODO:
СДЕЛАНО: Сделать, чтобы  агенты не сближались, чтобы их сплешем не било
Сделать, чтобы пушеры испольовали укрытия, а не тупо вперёд бежали
Улучшить броски бомб, т.к. они ОЧЕНЬ важны, основной урон исходит от них. Например, если видит, что можно кинуть в четверых разом, идёт туда, чтобы кинуть. Наверн вынести в стратегию бомбера, а когда все бомбы потратит, играет по своей роли.

1. 1 4 16 - Heavy
2. 5 2 32 - Pyro
3. 2 2 8 - Scout
4. 2 4 16 - Heavy
5. 5 6 32 - Sniper

'''
