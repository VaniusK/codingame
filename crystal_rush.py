# 930/3400, Gold League(6/942)
from __future__ import annotations
import sys
import math
from enum import Enum

ORE_THRESHOLD = 30

class Team(Enum):
    ALLY = 0
    ENEMY = 1

class Item(Enum):
    NONE = -1
    RADAR = 2
    TRAP = 3
    ORE = 4

class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
    
    def __eq__(self, other):
        if isinstance(other, Point):
            return (self.x, self.y) == (other.x, other.y)
        raise TypeError(f"Can't compare Point with {type(other)}")
    
    # Манхэттен
    def __sub__(self, other: Point) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"

class Cell:
    def __init__(self, position: Point, ore: int | None, hole: bool):
        self.position: Point = position
        self.__ore: int | None = ore
        self.previous_ore: int | None = ore
        self.predicted_ore: int | None = ore
        self.__hole: bool = hole
        self.previous_hole: bool = False
        self.ally_radar: bool = False
        self.radar_exploration_score: int = 0
    

    @property
    def hole(self):
        return self.__hole
    
    @hole.setter
    def hole(self, new_value: bool):
        self.previous_hole = self.__hole
        self.__hole = new_value
    
    @property
    def ore(self):
        return self.__ore
    
    @ore.setter
    def ore(self, new_value: int | None):
        self.previous_ore = self.ore
        self.__ore = new_value
        self.predicted_ore = self.__ore
    
    @property
    def has_ore(self) -> bool:
        return bool(self.predicted_ore and self.predicted_ore > 0)


class Robot:
    def __init__(self, robot_id, robot_team: Team, position: Point, inventory: Item):
        self.id: int = robot_id
        self.team: Team = robot_team
        self.__position: Point = position
        self.previous_position: Point | None = None
        self.inventory: Item = inventory
        self.__command: str | None = None
        self.radar_destination: Point | None = None
        self.is_camping: bool = False
        # __, чтобы своими грязными руками в вызов команды не лезли
    
    '''
    Мы не можем сразу выводить команду, потому что мы должны это делать
    по порядку. Если бы мы выводили сразу, мы обязаны были бы ставить
    команду сначала первому роботу, потом второму и тд.
    А так можем в любом порядке.
    '''
    def WAIT(self, message:str = ""):
        self.__command = f"WAIT {message}"
    
    def MOVE(self, position: Point, message: str = ""):
        self.__command = f"MOVE {position.x} {position.y} {message}"
    
    def DIG(self, position: Point, message: str = ""):
        self.__command = f"DIG {position.x} {position.y} {message}"
    
    def REQUEST(self, item: Item, message: str = ""):
        self.__command = f"REQUEST {item.name} {message}"
    
    def act(self):
        if not self.__command:
            self.WAIT("Я лосось поющий, на пляжу ляжущий")
        print(self.__command)
        self.__command = None
        # Если увидели поющего лосося - забыли обновить команду. 
        # Всё понятно и логично.
    
    @property
    def position(self) -> Point:
        return self.__position
    
    @position.setter
    def position(self, value: Point):
        self.previous_position = self.__position
        self.__position = value
    
    @property
    def is_alive(self) -> bool:
        return self.position.x != -1 and self.position.y != -1
        

class GameMap:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.field = [[Cell(Point(j, i), None, False) for j in range(width)] for i in range(height)]
        self.__cells = None
    
    def update_map(self, inputs: list[str]):
        for i in range(self.height):
            line = inputs[i].split()
            for j in range(self.width):
                ore =  line[2 * j]
                if ore == '?':
                    ore = None # unknown
                else:
                    ore = int(ore)
                cell = self.field[i][j]
                cell.ore = ore
                cell.hole = bool(int(line[2 * j + 1]))
                cell.ally_radar = False # Детектим в контроллере
    
    def is_valid(self, position: Point) -> bool:
        return position.x >= 0 and position.y >= 0 and position.y < self.height and position.x < self.width
    
    def __getitem__(self, point: Point):
        if isinstance(point, Point):
            if not self.is_valid(point):
                raise IndexError("Out of bounds")
            return self.field[point.y][point.x]
        else:
            raise TypeError("Invalid indexation")
    
    @property
    def cells(self) -> list[Cell]:
        if not self.__cells:
            self.__cells = [item for sublist in self.field for item in sublist]
        return self.__cells

class GameState:
    def __init__(self, width: int, height: int):
        self.width: int = width
        self.height: int = height
        self.ally_score: int = 0
        self.enemy_score: int = 0
        self.game_map: GameMap = GameMap(width, height)
        self.robots: dict[int, Robot] = dict()
        self.ally_robots: list[Robot] = []
        self.enemy_robots: list[Robot] = []
        self.radar_cooldown: int = 0
        self.trap_cooldown: int = 0
        self.ally_radars: list[Point] = []
        self.ally_traps: list[Point] = []
        self.is_first_turn = True


    def update_state(self):
        self.ally_radars = []
        self.ally_traps = []
        self.ally_score, self.enemy_score = [int(i) for i in input().split()]
        self.game_map.update_map([input() for _ in range(self.height)])
        entity_count, self.radar_cooldown, self.trap_cooldown = [int(i) for i in input().split()]
        for i in range(entity_count):
            entity_id, entity_type, x, y, item = [int(j) for j in input().split()]
            if entity_type in [0, 1]:
                if self.is_first_turn:
                    robot = Robot(entity_id, Team(entity_type), Point(x, y), Item(item))
                    self.robots[entity_id] = robot
                    if robot.team == Team.ALLY:
                        self.ally_robots.append(robot)
                    else:
                        self.enemy_robots.append(robot)
                else:
                    self.robots[entity_id].position = Point(x, y)
                    self.robots[entity_id].inventory = Item(item)
            elif entity_type == 2:
                self.ally_radars.append(Point(x, y))
                self.game_map[Point(x, y)].ally_radar = True
            elif entity_type == 3:
                self.ally_traps.append(Point(x, y))
        
        self.is_first_turn = False

class Controller:
    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.dangerous_cells = set()
        self.visible_ore: int = 0
    
    @property
    def game_map(self) -> GameMap:
        return self.game_state.game_map
    
    @property
    def ally_robots(self) -> list[Robot]:
        return self.game_state.ally_robots
    
    @property
    def enemy_robots(self) -> list[Robot]:
        return self.game_state.enemy_robots
    
    def game_step(self):
        self.game_state.update_state()

        self.detect_dangerous_cells()
        self.calculate_radar_exploration_scores()
        self.calculate_visible_ore()
        
        for robot in self.ally_robots:
            # Не тратим вычислительное время на мёртвых роботов
            # Пусть лосося поют
            if robot.is_alive:
                self.decide_robot_action(robot)

        # Указываем в любом порядке, act ТОЛЬКО по порядку.
        for robot in self.ally_robots:
            robot.act()
    
    def detect_dangerous_cells(self):
        for cell in self.game_map.cells:
            if (cell.hole and not cell.previous_hole) or (cell.ore is not None and cell.previous_ore is not None and cell.ore < cell.previous_ore):
                nearby_enemies = 0
                for enemy in self.enemy_robots:
                    if enemy.position - cell.position <= 1:
                        nearby_enemies += 1
                if nearby_enemies > 0:
                    self.dangerous_cells.add(cell.position)
    
    def calculate_visible_ore(self):
        self.visible_ore = 0
        for cell in self.game_map.cells:
            if cell.ore and not cell.position in self.dangerous_cells:
                self.visible_ore += cell.ore
    
    def calculate_radar_exploration_scores(self):
        for cell in self.game_map.cells:
            cell.radar_exploration_score = 0
            for xdiff in range(-4, 5):
                max_ydiff = 4 - abs(xdiff)
                for ydiff in range(-max_ydiff, max_ydiff + 1):
                    new_position = cell.position + Point(xdiff, ydiff)
                    if not self.game_map.is_valid(new_position):
                        continue
                    if self.game_map[new_position].ore == None:
                        cell.radar_exploration_score += 1
    
    def calculate_radar_position_score(self, robot: Robot, position: Point) -> float:
        EXPLORATION_BONUS = 1
        ORE_BONUS = 30
        TRAP_BONUS = -1000
        DISTANCE_COEFF = 0.01

        score: float = 0
        score += self.game_map[position].radar_exploration_score * EXPLORATION_BONUS * (1 - DISTANCE_COEFF * position.x)
        if self.game_map[position].has_ore:
            score += ORE_BONUS * (1 - DISTANCE_COEFF * (robot.position - position))
        if position in self.dangerous_cells:
            score += TRAP_BONUS
        
        return score
    
    def decide_radar_position(self, robot: Robot) -> Point:
        cells = self.game_map.cells
        choosen_cell = max(cells, key=lambda x: self.calculate_radar_position_score(robot, x.position))
        return choosen_cell.position

    
    def decide_robot_action(self, robot: Robot):
        robot.is_camping = False
        if robot.inventory == Item.ORE:
            # Несёшь руду - ну и неси
            robot.MOVE(Point(0, robot.position.y), "Несу руду")
            return
        
        if robot.inventory == Item.RADAR:
            robot.radar_destination = self.decide_radar_position(robot)
            robot.DIG(robot.radar_destination, "Несу радар")
            cell = self.game_map[robot.radar_destination]
            if cell.ore:
                cell.ore -= 1
            return
        
        if self.visible_ore < ORE_THRESHOLD and self.game_state.radar_cooldown == 0 and robot.position.x == 0:
            robot.REQUEST(Item.RADAR, "Иду за радаром")
            self.game_state.radar_cooldown = -1
            robot.radar_destination = self.decide_radar_position(robot)
            cell = self.game_map[robot.radar_destination]
            if cell.ore:
                cell.ore -= 1
            return
        
        if self.visible_ore > 0:
            ore_cells = [cell for cell in self.game_map.cells if cell.has_ore and not cell.position in self.dangerous_cells]
            if ore_cells:
                cell = min(ore_cells, key=lambda x: x.position - robot.position)
                robot.DIG(cell.position, "Иду копать руду")
                # Чтобы другие за пустой не бегали. На следующем ходу
                # обновится правильным значением
                if cell.predicted_ore:
                    cell.predicted_ore -= 1
                return
        
        if not any([robot.is_camping for robot in self.ally_robots]):
            robot.MOVE(Point(0, robot.position.y), "Иду на базу ждать айтем")
            robot.is_camping = True
            return
        
        radar_holders = [robot for robot in self.ally_robots if robot.inventory == Item.RADAR]
        if radar_holders:
            closest_radar_holder = min(radar_holders, key=lambda point: point.position - robot.position + point.position.x)
            robot.MOVE(closest_radar_holder.position, "Иду за радарщиком")
            return


        

        
        
        
            


width, height = [int(i) for i in input().split()]

game_state = GameState(width, height)

controller = Controller(game_state)

# game loop
while True:
    controller.game_step()
