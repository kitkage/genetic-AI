# capture.py
# ----------
# Licensing Information: Please do not distribute or publish solutions to this
# project. You are free to use and extend these projects for educational
# purposes. The Pacman AI projects were developed at UC Berkeley, primarily by
# John DeNero (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# For more info, see http://inst.eecs.berkeley.edu/~cs188/sp09/pacman.html
from baselineTeam import DefensiveReflexAgent, OffensiveReflexAgent

"""
Capture.py holds the logic for Pacman capture the flag.

  (i)  Your interface to the pacman world:
          Pacman is a complex environment.  You probably don't want to
          read through all of the code we wrote to make the game runs
          correctly.  This section contains the parts of the code
          that you will need to understand in order to complete the
          project.  There is also some code in game.py that you should
          understand.

  (ii)  The hidden secrets of pacman:
          This section contains all of the logic code that the pacman
          environment uses to decide who can move where, who dies when
          things collide, etc.  You shouldn't need to read this section
          of code, but you can if you want.

  (iii) Framework to start a game:
          The final section contains the code for reading the command
          you use to set up the game, then starting up a new game, along with
          linking in all the external parts (agent functions, graphics).
          Check this section out to see all the options available to you.

To play your first game, type 'python capture.py' from the command line.
The keys are
  P1: 'a', 's', 'd', and 'w' to move
  P2: 'l', ';', ',' and 'p' to move
"""
from game import GameStateData
from game import Game
from game import Directions
from game import Actions
from util import nearestPoint
from util import manhattanDistance
from game import Grid
from game import Configuration
from game import Agent
from game import reconstituteGrid
from myTeam import GeneticAgent
import sys, util, types, time, random
import keyboardAgents

# If you change these, you won't affect the server, so you can't cheat
KILL_POINTS = 10
SONAR_NOISE_RANGE = 13 # Must be odd
SONAR_NOISE_VALUES = [i - (SONAR_NOISE_RANGE - 1)/2 for i in range(SONAR_NOISE_RANGE)]
SIGHT_RANGE = 100000 # Manhattan distance
MIN_FOOD = 2

SCARED_TIME = 40

def noisyDistance(pos1, pos2):
  return int(util.manhattanDistance(pos1, pos2) + random.choice(SONAR_NOISE_VALUES))

###################################################
# YOUR INTERFACE TO THE PACMAN WORLD: A GameState #
###################################################

class GameState:
  """
  A GameState specifies the full game state, including the food, capsules,
  agent configurations and score changes.

  GameStates are used by the Game object to capture the actual state of the game and
  can be used by agents to reason about the game.

  Much of the information in a GameState is stored in a GameStateData object.  We
  strongly suggest that you access that data via the accessor methods below rather
  than referring to the GameStateData object directly.
  """

  ####################################################
  # Accessor methods: use these to access state data #
  ####################################################

  def getLegalActions( self, agentIndex=0 ):
    """
    Returns the legal actions for the agent specified.
    """
    return AgentRules.getLegalActions( self, agentIndex )

  def generateSuccessor( self, agentIndex, action):
    """
    Returns the successor state (a GameState object) after the specified agent takes the action.
    """
    # Copy current state
    state = GameState(self)

    # Find appropriate rules for the agent
    AgentRules.applyAction( state, action, agentIndex )
    AgentRules.checkDeath(state, agentIndex)
    AgentRules.decrementTimer(state.data.agentStates[agentIndex])

    # Book keeping
    state.data._agentMoved = agentIndex
    state.data.score += state.data.scoreChange
    state.data.timeleft = self.data.timeleft - 1
    return state

  def getAgentState(self, index):
    return self.data.agentStates[index]

  def getAgentPosition(self, index):
    """
    Returns a location tuple if the agent with the given index is observable;
    if the agent is unobservable, returns None.
    """
    agentState = self.data.agentStates[index]
    ret = agentState.getPosition()
    if ret:
      return tuple(int(x) for x in ret)
    return ret

  def getNumAgents( self ):
    return len( self.data.agentStates )

  def getScore( self ):
    """
    Returns a number corresponding to the current score.
    """
    return self.data.score

  def getRedFood(self):
    """
    Returns a matrix of food that corresponds to the food on the red team's side.
    For the matrix m, m[x][y]=true if there is food in (x,y) that belongs to
    red (meaning red is protecting it, blue is trying to eat it).
    """
    return halfGrid(self.data.food, red = True)

  def getBlueFood(self):
    """
    Returns a matrix of food that corresponds to the food on the blue team's side.
    For the matrix m, m[x][y]=true if there is food in (x,y) that belongs to
    blue (meaning blue is protecting it, red is trying to eat it).
    """
    return halfGrid(self.data.food, red = False)

  def getRedCapsules(self):
    return halfList(self.data.capsules, self.data.food, red = True)

  def getBlueCapsules(self):
    return halfList(self.data.capsules, self.data.food, red = False)

  def getWalls(self):
    """
    Just like getFood but for walls
    """
    return self.data.layout.walls

  def hasFood(self, x, y):
    """
    Returns true if the location (x,y) has food, regardless of
    whether it's blue team food or red team food.
    """
    return self.data.food[x][y]

  def hasWall(self, x, y):
    """
    Returns true if (x,y) has a wall, false otherwise.
    """
    return self.data.layout.walls[x][y]

  def isOver( self ):
    return self.data._win

  def getRedTeamIndices(self):
    """
    Returns a list of agent index numbers for the agents on the red team.
    """
    return self.redTeam[:]

  def getBlueTeamIndices(self):
    """
    Returns a list of the agent index numbers for the agents on the blue team.
    """
    return self.blueTeam[:]

  def isOnRedTeam(self, agentIndex):
    """
    Returns true if the agent with the given agentIndex is on the red team.
    """
    return self.teams[agentIndex]

  def getAgentDistances(self):
    """
    Returns a noisy distance to each agent.
    """
    if 'agentDistances' in dir(self) :
      return self.agentDistances
    else:
      return None

  def getDistanceProb(self, trueDistance, noisyDistance):
    "Returns the probability of a noisy distance given the true distance"
    if noisyDistance - trueDistance in SONAR_NOISE_VALUES:
      return 1.0/SONAR_NOISE_RANGE
    else:
      return 0

  def getInitialAgentPosition(self, agentIndex):
    "Returns the initial position of an agent."
    return self.data.layout.agentPositions[agentIndex][1]

  def getCapsules(self):
    """
    Returns a list of positions (x,y) of the remaining capsules.
    """
    return self.data.capsules

  #############################################
  #             Helper methods:               #
  # You shouldn't need to call these directly #
  #############################################

  def __init__( self, prevState = None ):
    """
    Generates a new state by copying information from its predecessor.
    """
    if prevState != None: # Initial state
      self.data = GameStateData(prevState.data)
      self.blueTeam = prevState.blueTeam
      self.redTeam = prevState.redTeam
      self.data.timeleft = prevState.data.timeleft

      self.teams = prevState.teams
      self.agentDistances = prevState.agentDistances
    else:
      self.data = GameStateData()
      self.agentDistances = []

  def deepCopy( self ):
    state = GameState( self )
    state.data = self.data.deepCopy()
    state.data.timeleft = self.data.timeleft

    state.blueTeam = self.blueTeam[:]
    state.redTeam = self.redTeam[:]
    state.teams = self.teams[:]
    state.agentDistances = self.agentDistances[:]
    return state

  def makeObservation(self, index):
    state = self.deepCopy()

    # Adds the sonar signal
    pos = state.getAgentPosition(index)
    n = state.getNumAgents()
    distances = [noisyDistance(pos, state.getAgentPosition(i)) for i in range(n)]
    state.agentDistances = distances

    # Remove states of distant opponents
    if index in self.blueTeam:
      team = self.blueTeam
      otherTeam = self.redTeam
    else:
      otherTeam = self.blueTeam
      team = self.redTeam

    for enemy in otherTeam:
      seen = False
      enemyPos = state.getAgentPosition(enemy)
      for teammate in team:
        if util.manhattanDistance(enemyPos, state.getAgentPosition(teammate)) <= SIGHT_RANGE:
          seen = True
      if not seen: state.data.agentStates[enemy].configuration = None
    return state

  def __eq__( self, other ):
    """
    Allows two states to be compared.
    """
    if other == None: return False
    return self.data == other.data

  def __hash__( self ):
    """
    Allows states to be keys of dictionaries.
    """
    return int(hash( self.data ))

  def __str__( self ):

    return str(self.data)

  def initialize( self, layout, numAgents):
    """
    Creates an initial game state from a layout array (see layout.py).
    """
    self.data.initialize(layout, numAgents)
    positions = [a.configuration for a in self.data.agentStates]
    self.blueTeam = [i for i,p in enumerate(positions) if not self.isRed(p)]
    self.redTeam = [i for i,p in enumerate(positions) if self.isRed(p)]
    self.teams = [self.isRed(p) for p in positions]

  def isRed(self, configOrPos):
    width = self.data.layout.width
    if type(configOrPos) == type( (0,0) ):
      return configOrPos[0] < width / 2
    else:
      return configOrPos.pos[0] < width / 2

def halfGrid(grid, red):
  halfway = grid.width / 2
  halfgrid = Grid(grid.width, grid.height, False)
  if red:    xrange = range(halfway)
  else:       xrange = range(halfway, grid.width)

  for y in range(grid.height):
    for x in xrange:
      if grid[x][y]: halfgrid[x][y] = True

  return halfgrid

def halfList(l, grid, red):
  halfway = grid.width / 2
  newList = []
  for x,y in l:
    if red and x <= halfway: newList.append((x,y))
    elif not red and x > halfway: newList.append((x,y))
  return newList

############################################################################
#                     THE HIDDEN SECRETS OF PACMAN                         #
#                                                                          #
# You shouldn't need to look through the code in this section of the file. #
############################################################################

COLLISION_TOLERANCE = 0.7 # How close ghosts must be to Pacman to kill

class CaptureRules:
  """
  These game rules manage the control flow of a game, deciding when
  and how the game starts and ends.
  """

  def __init__(self, quiet = False):
    self.quiet = quiet

  def newGame( self, layout, agents, display, length, muteAgents, catchExceptions ):
    initState = GameState()
    initState.initialize( layout, len(agents) )
    starter = random.randint(0,1)
#    print('%s team starts' % ['Red', 'Blue'][starter])
    game = Game(agents, display, self, startingIndex=starter, muteAgents=muteAgents, catchExceptions=catchExceptions)
    game.state = initState
    game.length = length
    game.state.data.timeleft = length
    if 'drawCenterLine' in dir(display):
      display.drawCenterLine()
    self._initBlueFood = initState.getBlueFood().count()
    self._initRedFood = initState.getRedFood().count()
    return game

  def process(self, state, game):
    """
    Checks to see whether it is time to end the game.
    """
    if 'moveHistory' in dir(game):
      if len(game.moveHistory) == game.length:
        state.data._win = True

    if state.isOver():
      game.gameOver = True
      if not game.rules.quiet:
        if state.getRedFood().count() == MIN_FOOD:
          print 'The Blue team has captured all but %d of the opponents\' dots.' % MIN_FOOD
        if state.getBlueFood().count() == MIN_FOOD:
          print 'The Red team has captured all but %d of the opponents\' dots.' % MIN_FOOD
        if state.getBlueFood().count() > MIN_FOOD and state.getRedFood().count() > MIN_FOOD:
          print 'Time is up.'
          if state.data.score == 0: print 'Tie game!'
          else:
            winner = 'Red'
            if state.data.score < 0: winner = 'Blue'
            print 'The %s team wins by %d points.' % (winner, abs(state.data.score))

  def getProgress(self, game):
    blue = 1.0 - (game.state.getBlueFood().count() / float(self._initBlueFood))
    red = 1.0 - (game.state.getRedFood().count() / float(self._initRedFood))
    moves = len(self.moveHistory) / float(game.length)

    # return the most likely progress indicator, clamped to [0, 1]
    return min(max(0.75 * max(red, blue) + 0.25 * moves, 0.0), 1.0)

  def agentCrash(self, game, agentIndex):
    if agentIndex % 2 == 0:
      print "Red agent crashed"
      game.state.data.score = -1
    else:
      print "Blue agent crashed"
      game.state.data.score = 1

  def getMaxTotalTime(self, agentIndex):
    return 900  # Move limits should prevent this from ever happening

  def getMaxStartupTime(self, agentIndex):
    return 15 # 15 seconds for registerInitialState

  def getMoveWarningTime(self, agentIndex):
    return 1  # One second per move

  def getMoveTimeout(self, agentIndex):
    return 3  # Three seconds results in instant forfeit

  def getMaxTimeWarnings(self, agentIndex):
    return 2  # Third violation loses the game

class AgentRules:
  """
  These functions govern how each agent interacts with her environment.
  """

  def getLegalActions( state, agentIndex ):
    """
    Returns a list of legal actions (which are both possible & allowed)
    """
    agentState = state.getAgentState(agentIndex)
    conf = agentState.configuration
    possibleActions = Actions.getPossibleActions( conf, state.data.layout.walls )
    return AgentRules.filterForAllowedActions( agentState, possibleActions)
  getLegalActions = staticmethod( getLegalActions )

  def filterForAllowedActions(agentState, possibleActions):
    return possibleActions
  filterForAllowedActions = staticmethod( filterForAllowedActions )


  def applyAction( state, action, agentIndex ):
    """
    Edits the state to reflect the results of the action.
    """
    legal = AgentRules.getLegalActions( state, agentIndex )
    if action not in legal:
      raise Exception("Illegal action " + str(action))

    # Update Configuration
    agentState = state.data.agentStates[agentIndex]
    speed = 1.0
    # if agentState.isPacman: speed = 0.5
    vector = Actions.directionToVector( action, speed )
    oldConfig = agentState.configuration
    agentState.configuration = oldConfig.generateSuccessor( vector )

    # Eat
    next = agentState.configuration.getPosition()
    nearest = nearestPoint( next )
    if agentState.isPacman and manhattanDistance( nearest, next ) <= 0.9 :
      AgentRules.consume( nearest, state, state.isOnRedTeam(agentIndex) )

    # Change agent type
    if next == nearest:
      agentState.isPacman = [state.isOnRedTeam(agentIndex), state.isRed(agentState.configuration)].count(True) == 1
  applyAction = staticmethod( applyAction )

  def consume( position, state, isRed ):
    x,y = position
    # Eat food
    if state.data.food[x][y]:
      score = -1
      if isRed: score = 1
      state.data.scoreChange += score

      state.data.food = state.data.food.copy()
      state.data.food[x][y] = False
      state.data._foodEaten = position
      if (isRed and state.getBlueFood().count() == MIN_FOOD) or (not isRed and state.getRedFood().count() == MIN_FOOD):
        state.data._win = True

    # Eat capsule
    if isRed: myCapsules = state.getBlueCapsules()
    else: myCapsules = state.getRedCapsules()
    if( position in myCapsules ):
      state.data.capsules.remove( position )
      state.data._capsuleEaten = position

      # Reset all ghosts' scared timers
      if isRed: otherTeam = state.getBlueTeamIndices()
      else: otherTeam = state.getRedTeamIndices()
      for index in otherTeam:
        state.data.agentStates[index].scaredTimer = SCARED_TIME

  consume = staticmethod( consume )

  def decrementTimer(state):
    timer = state.scaredTimer
    if timer == 1:
      state.configuration.pos = nearestPoint( state.configuration.pos )
    state.scaredTimer = max( 0, timer - 1 )
  decrementTimer = staticmethod( decrementTimer )

  def checkDeath( state, agentIndex):
    agentState = state.data.agentStates[agentIndex]
    if state.isOnRedTeam(agentIndex):
      otherTeam = state.getBlueTeamIndices()
    else:
      otherTeam = state.getRedTeamIndices()
    if agentState.isPacman:
      for index in otherTeam:
        otherAgentState = state.data.agentStates[index]
        if otherAgentState.isPacman: continue
        ghostPosition = otherAgentState.getPosition()
        if ghostPosition == None: continue
        if manhattanDistance( ghostPosition, agentState.getPosition() ) <= COLLISION_TOLERANCE:
          #award points to the other team for killing Pacmen
          if otherAgentState.scaredTimer <= 0:
            score = KILL_POINTS
            if state.isOnRedTeam(agentIndex):
              score = -score
            state.data.scoreChange += score
            agentState.isPacman = False
            agentState.configuration = agentState.start
            agentState.scaredTimer = 0
          else:
            score = KILL_POINTS
            if state.isOnRedTeam(agentIndex):
              score = -score
            state.data.scoreChange += score
            otherAgentState.isPacman = False
            otherAgentState.configuration = otherAgentState.start
            otherAgentState.scaredTimer = 0
    else: # Agent is a ghost
      for index in otherTeam:
        otherAgentState = state.data.agentStates[index]
        if not otherAgentState.isPacman: continue
        pacPos = otherAgentState.getPosition()
        if pacPos == None: continue
        if manhattanDistance( pacPos, agentState.getPosition() ) <= COLLISION_TOLERANCE:
          #award points to the other team for killing Pacmen
          if agentState.scaredTimer <= 0:
            score = KILL_POINTS
            if not state.isOnRedTeam(agentIndex):
              score = -score
            state.data.scoreChange += score
            otherAgentState.isPacman = False
            otherAgentState.configuration = otherAgentState.start
            otherAgentState.scaredTimer = 0
          else:
            score = KILL_POINTS
            if state.isOnRedTeam(agentIndex):
              score = -score
            state.data.scoreChange += score
            agentState.isPacman = False
            agentState.configuration = agentState.start
            agentState.scaredTimer = 0
  checkDeath = staticmethod( checkDeath )

  def placeGhost(state, ghostState):
    ghostState.configuration = ghostState.start
  placeGhost = staticmethod( placeGhost )

#############################
# FRAMEWORK TO START A GAME #
#############################

def default(str):
  return str + ' [Default: %default]'

def parseAgentArgs(str):
  if str == None or str == '': return {}
  pieces = str.split(',')
  opts = {}
  for p in pieces:
    if '=' in p:
      key, val = p.split('=')
    else:
      key,val = p, 1
    opts[key] = val
  return opts

def readCommand( argv ):
  """
  Processes the command used to run pacman from the command line.
  """
  from optparse import OptionParser
  usageStr = """
  USAGE:      python pacman.py <options>
  EXAMPLES:   (1) python capture.py
                  - starts a game with two baseline agents
              (2) python capture.py --keys0
                  - starts a two-player interactive game where the arrow keys control agent 0, and all other agents are baseline agents
              (3) python capture.py -r baselineTeam -b myTeam
                  - starts a fully automated game where the red team is a baseline team and blue team is myTeam
  """
  parser = OptionParser(usageStr)

  parser.add_option('-r', '--red', help=default('Red team'),
                    default='baselineTeam')
  parser.add_option('-b', '--blue', help=default('Blue team'),
                    default='baselineTeam')
  parser.add_option('--redOpts', help=default('Options for red team (e.g. first=keys)'),
                    default='')
  parser.add_option('--blueOpts', help=default('Options for blue team (e.g. first=keys)'),
                    default='')
  parser.add_option('--keys0', help='Make agent 0 (first red player) a keyboard agent', action='store_true',default=False)
  parser.add_option('--keys1', help='Make agent 1 (second red player) a keyboard agent', action='store_true',default=False)
  parser.add_option('--keys2', help='Make agent 2 (first blue player) a keyboard agent', action='store_true',default=False)
  parser.add_option('--keys3', help='Make agent 3 (second blue player) a keyboard agent', action='store_true',default=False)
  parser.add_option('-l', '--layout', dest='layout',
                    help=default('the LAYOUT_FILE from which to load the map layout; use RANDOM for a random maze; use RANDOM<seed> to use a specified random seed, e.g., RANDOM23'),
                    metavar='LAYOUT_FILE', default='defaultCapture')
  parser.add_option('-t', '--textgraphics', action='store_true', dest='textgraphics',
                    help='Display output as text only', default=False)

  parser.add_option('-q', '--quiet', action='store_true',
                    help='Display minimal output and no graphics', default=False)

  parser.add_option('-Q', '--super-quiet', action='store_true', dest="super_quiet",
                    help='Same as -q but agent output is also suppressed', default=False)

  parser.add_option('-z', '--zoom', type='float', dest='zoom',
                    help=default('Zoom in the graphics'), default=1)
  parser.add_option('-i', '--time', type='int', dest='time',
                    help=default('TIME limit of a game in moves'), default=17, metavar='TIME')
  parser.add_option('-n', '--numGames', type='int',
                    help=default('Number of games to play'), default=1)
  parser.add_option('-f', '--fixRandomSeed', action='store_true',
                    help='Fixes the random seed to always play the same game', default=False)
  parser.add_option('--record', action='store_true',
                    help='Writes game histories to a file (named by the time they were played)', default=False)
  parser.add_option('--replay', default=None,
                    help='Replays a recorded game file.')
  parser.add_option('-x', '--numTraining', dest='numTraining', type='int',
                    help=default('How many episodes are training (suppresses output)'), default=0)
  parser.add_option('-c', '--catchExceptions', action='store_true', default=False,
                    help='Catch exceptions and enforce time limits')

  options, otherjunk = parser.parse_args(argv)
  assert len(otherjunk) == 0, "Unrecognized options: " + str(otherjunk)
  args = dict()

  # Choose a display format
  #if options.pygame:
  #   import pygameDisplay
  #    args['display'] = pygameDisplay.PacmanGraphics()
  if options.textgraphics:
    import textDisplay
    args['display'] = textDisplay.PacmanGraphics()
  elif options.quiet:
    import textDisplay
    args['display'] = textDisplay.NullGraphics()
  elif options.super_quiet:
    import textDisplay
    args['display'] = textDisplay.NullGraphics()
    args['muteAgents'] = True
  else:
    import captureGraphicsDisplay
    # Hack for agents writing to the display
    captureGraphicsDisplay.FRAME_TIME = 0
    args['display'] = captureGraphicsDisplay.PacmanGraphics(options.red, options.blue, options.zoom, 0, capture=True)
    import __main__
    __main__.__dict__['_display'] = args['display']


  args['redTeamName'] = options.red
  args['blueTeamName'] = options.blue

  if options.fixRandomSeed: random.seed('cs188')

  # Special case: recorded games don't use the runGames method or args structure
  if options.replay != None:
    print 'Replaying recorded game %s.' % options.replay
    import cPickle
    recorded = cPickle.load(open(options.replay))
    recorded['display'] = args['display']
    replayGame(**recorded)
    sys.exit(0)

  # Choose a pacman agent
  redArgs, blueArgs = parseAgentArgs(options.redOpts), parseAgentArgs(options.blueOpts)
  if options.numTraining > 0:
    redArgs['numTraining'] = options.numTraining
    blueArgs['numTraining'] = options.numTraining
  nokeyboard = options.textgraphics or options.quiet or options.numTraining > 0
  print '\nRed team %s with %s:' % (options.red, redArgs)
  redAgents = loadAgents(True, options.red, nokeyboard, redArgs)
  print '\nBlue team %s with %s:' % (options.blue, blueArgs)
  blueAgents = loadAgents(False, options.blue, nokeyboard, blueArgs)
  args['agents'] = sum([list(el) for el in zip(redAgents, blueAgents)],[]) # list of agents

  numKeyboardAgents = 0
  for index, val in enumerate([options.keys0, options.keys1, options.keys2, options.keys3]):
    if not val: continue
    if numKeyboardAgents == 0:
      agent = keyboardAgents.KeyboardAgent(index)
    elif numKeyboardAgents == 1:
      agent = keyboardAgents.KeyboardAgent2(index)
    else:
      raise Exception('Max of two keyboard agents supported')
    numKeyboardAgents += 1
    args['agents'][index] = agent

  # Choose a layout
  import layout
  if options.layout.startswith('RANDOM'):
    args['layout'] = layout.Layout(randomLayout(int(options.layout[6:])).split('\n'))
  elif options.layout.lower().find('capture') == -1:
    raise Exception( 'You must use a capture layout with capture.py')
  else:
    args['layout'] = layout.getLayout( options.layout )

  if args['layout'] == None: raise Exception("The layout " + options.layout + " cannot be found")
  args['length'] = options.time
  args['numGames'] = options.numGames
  args['numTraining'] = options.numTraining
  args['record'] = options.record
  args['catchExceptions'] = options.catchExceptions
  return args

def randomLayout(seed = None):
  if not seed:
    seed = random.randint(0,99999999)
  # layout = 'layouts/random%08dCapture.lay' % seed
  # print 'Generating random layout in %s' % layout
  import mazeGenerator
  return mazeGenerator.generateMaze(seed)

import traceback
def loadAgents(isRed, factory, textgraphics, cmdLineArgs):
  "Calls agent factories and returns lists of agents"
  try:
    module = __import__(factory)
  except ImportError:
    print 'Error: The team "' + factory + '" could not be loaded! '
    traceback.print_exc()
    return [None for i in range(2)]

  args = dict()
  args.update(cmdLineArgs)  # Add command line args with priority

  print "Loading Team:", factory
  print "Arguments:", args

  try:
    createTeamFunc = getattr(module, 'createTeam')
  except AttributeError:
    print 'Error: The team "' + factory + '" could not be loaded! '
    traceback.print_exc()
    return [None for i in range(2)]

  indexAddend = 0
  if not isRed:
    indexAddend = 1
  indices = [2*i + indexAddend for i in range(2)]
  return createTeamFunc(indices[0], indices[1], isRed, **args)

def replayGame( layout, agents, actions, display, length, redTeamName, blueTeamName ):
    rules = CaptureRules()
    game = rules.newGame( layout, agents, display, length, False, False )
    state = game.state
    display.redTeam = redTeamName
    display.blueTeam = blueTeamName
    display.initialize(state.data)

    for action in actions:
      # Execute the action
      state = state.generateSuccessor( *action )
      # Change the display
      display.update( state.data )
      # Allow for game specific conditions (winning, losing, etc.)
      rules.process(state, game)

    display.finish()

def runGames( layout, agents, display, length, numGames, record, numTraining, redTeamName, blueTeamName, muteAgents=False, catchExceptions=False ):

  rules = CaptureRules()
  games = []

  if numTraining > 0:
    print 'Playing %d training games' % numTraining

  for i in range( numGames ):
    beQuiet = i < numTraining
    if beQuiet:
        # Suppress output and graphics
        import textDisplay
        gameDisplay = textDisplay.NullGraphics()
        rules.quiet = True
    else:
        gameDisplay = display
        rules.quiet = False
    g = rules.newGame( layout, agents, gameDisplay, length, muteAgents, catchExceptions )
    g.run()
    
    if not beQuiet: games.append(g)

    g.record = None
    if record:
      import cPickle, game
      components = {'layout': layout, 'agents': [game.Agent() for a in agents], 'actions': g.moveHistory, 'length': length, 'redTeamName': redTeamName, 'blueTeamName':blueTeamName }
      print "recorded"
      g.record = cPickle.dumps(components)
      with open('replay','wb') as f:
        f.write(g.record)

  if numGames > 1:
    scores = [game.state.data.score for game in games]
    redWinRate = [s > 0 for s in scores].count(True)/ float(len(scores))
    blueWinRate = [s < 0 for s in scores].count(True)/ float(len(scores))
    print 'Average Score:', sum(scores) / float(len(scores))
    print 'Scores:       ', ', '.join([str(score) for score in scores])
    print 'Red Win Rate:  %d/%d (%.2f)' % ([s > 0 for s in scores].count(True), len(scores), redWinRate)
    print 'Blue Win Rate: %d/%d (%.2f)' % ([s < 0 for s in scores].count(True), len(scores), blueWinRate)
    print 'Record:       ', ', '.join([('Blue', 'Tie', 'Red')[max(0, min(2, 1 + s))] for s in scores])
  return games

def evalGame(value1, value2,display):
        """first value is red"""
        #value2 = [0.0020411299229444496, 0.005905575938833599, 0.03566795869729389, 0.05777155699043593, 0.11918689663959615, 0.17219955847603657, 0.0005020373604024941, 0.0005864789816226922, 0.00018953404735489913, 0.004890404560273808, 0.001846138094062659, 0.0008995799399871566, 0.044730023830092655, 0.17540973730389617, 0.08369432657312995, 0.012319235935014695, 0.07790746678514437, 0.036510412017216394, 0.0020365079241264315, 0.0013310425810684173, 0.10214535867752587, 0.062229038723940686]
        #agents=[OffensiveReflexAgent(0),GeneticAgent(1,0.1,value2[0:11]),DefensiveReflexAgent(2),GeneticAgent(3,0.1,value2[11:22])]
        agents=[GeneticAgent(0,0.1,value1[0:11]),GeneticAgent(1,0.1,value2[0:11]),GeneticAgent(2,0.1,value1[11:22]),GeneticAgent(3,0.1,value2[11:22])]
        rules = CaptureRules()
        import textDisplay
        gameDisplay = textDisplay.NullGraphics()
        rules.quiet = True#options['length'] options['display']
        if display:
            gameDisplay = options['display']
        g = rules.newGame( options['layout'], agents,gameDisplay, 1200, False, False )
        g.run()
        if g.state.getRedFood().count() == MIN_FOOD:
            return 0
        elif g.state.getBlueFood().count() == MIN_FOOD:
            return 1
        elif g.state.data.score < 0:
            return 1
        else:
            return 0
     
  
if __name__ == '__main__':
  """
  The main function called when pacman.py is run
  from the command line:

  > python capture.py

  See the usage string for more details.

  > python capture.py --help
  """
  options = readCommand( sys.argv[1:] ) # Get game components based on input
  runGames(**options)





geneLength = 22
probs = [0.1544200202,0.1576537777,0.1512525920,0.1363637389,0.1155293991,0.09197790668,0.06881319473,0.04837899685,0.03196234444,0.01984342642,0.01157685408,0.006346873535,0.003269821209,0.001583005700,0.0007201693720,0.0003078788466]
def mutate():
    t = random.random()
    for i in range(0,16):
        t-=probs[i]
        if t<0:
            return i/16.+random.random()/16
    return 1

def crossover(gene1,gene2):
    child1 = [];
    child2 = [];
    for i in range(0,len(gene1)):
        if random.random()<1./len(gene1):
            child1.append(mutate())
            child2.append(mutate())
        elif random.random()<0.5:
            child1.append(gene1[i])
            child2.append(gene2[i])
        else:
            child1.append(gene2[i])
            child2.append(gene1[i])
    s1 = sum(child1)
    s2 = sum(child2)
    if s1==0:
        child1 = [1]*len(gene1)
        s1 = len(gene1)
    if s2==0:
        child2 = [1]*len(gene2)
        s2 = len(gene2)
    for i in range(0,len(gene1)):
        child1[i]/=s1
        child2[i]/=s2
    return child1,child2

def randGene():
    gene = [];
    for i in range(0,geneLength):
        gene.append(mutate())
    s = sum(gene)
    if s==0:
        gene = [1]*geneLength
        s = geneLength
    for i in range(0,geneLength):
        gene[i]/=s
        gene[i]/=s
    return gene

population = 16
genes = []
for i in range(0,population):
    genes.append((0,randGene(),`i`,0))

def compete(gene1,gene2,display):
    return evalGame(gene1,gene2,display)

def Genetic_Algorithm(genes):
    population = len(genes)
    random.shuffle(genes)
    for competition in range(0,population/2):
        winner = compete(genes[competition][1],genes[population-competition-1][1],display)
        if winner:
            tempgene = genes[competition]
            genes[competition] = genes[population-competition-1]
            genes[population-competition-1] = tempgene
        if genes[population-competition-1][0]:
            for i in range(population/2-1,-1,-1):
                if i!=competition and not genes[i][0]:
                    genes[i] = (0,)+genes[population-competition-1][1:]
                    break
    print("Round 1 over")
    genes = genes[0:population/2]
    for competition in range(0,population/4):
        winner = compete(genes[competition][1],genes[population/2-competition-1][1],display)
        if winner:
            tempgene = genes[competition]
            genes[competition] = genes[population/2-competition-1]
            genes[population/2-competition-1] = tempgene
        if genes[population/2-competition-1][0]:
            for i in range(population/4-1,-1,-1):
                if i!=competition and not genes[i][0]:
                    genes[i] = (0,)+genes[population/2-competition-1][1:]
                    break
    print("Round 2 over")
    genes = genes[0:population/4]
    for competition in range(0,population/8):
        winner = compete(genes[competition][1],genes[population/4-competition-1][1],display)
        if winner:
            tempgene = genes[competition]
            genes[competition] = genes[population/4-competition-1]
            genes[population/4-competition-1] = tempgene
        genes[competition] = (1,)+genes[competition][1:3]+(genes[competition][3]+1,)
        genes[population/4-competition-1] = (0,)+genes[population/4-competition-1][1:3]+(genes[population/4-competition-1][3]+1,)
    tomake = population/4*3
    while tomake>0:
        for i in range(0,population/4-1):
            for j in range(i+1,population/4):
                if tomake<=0:
                    break
                children = crossover(genes[i][1],genes[j][1])
                genes.append((0,children[0],genes[i][2],0))
                genes.append((0,children[1],genes[j][2],0))
                tomake-=2
            if tomake<=0:
                break
    return genes

def printWeights(gene):
    print("Food Hunting: \t"+`gene[0]`)
    print("Score: \t\t"+`gene[1]`)
    print("Pacman Hunting: "+`gene[2]`)
    print("Preventing: \t"+`gene[3]`)
    print("Eating Ghosts: \t"+ `gene[4]`)
    print("Running: \t"+`gene[5]`)
    print("Capsule: \t"+`gene[6]`)
    print("Countdown: \t"+`gene[7]`)
    print("Border: \t"+`gene[8]`)
    print("Paths: \t\t"+`gene[9]`)
    print("Separation: \t"+`gene[10]`)

maxwins = 0
generation = 0
import thread
def keypress():
    global display
    display = False
    while True:
        char = sys.stdin.read(1)
        if char=='1':
            display = True
        elif char=='0':
            display = False
thread.start_new(keypress,())
display = True
while maxwins<10:
    genes = Genetic_Algorithm(genes)
    maxwins = max(genes[0][3],max(genes[1][3],max(genes[2][3],genes[3][3])))
    print("Oldest Competitor: "+`maxwins`)
    print(genes[0])
    printWeights(genes[0][1])
    print(genes[1])
    printWeights(genes[1][1])
    generation+=1

