import collections
import itertools
import random
import csv

import sys
import os

from player import Agent

from collections import OrderedDict
from collections import deque
from deck import Deck
from player import Player
from strategy import Strategy

from deuces import Card
from deuces import Evaluator


#### USER-DEFINED VARIABLES ####
N_PLAYERS = 3 # TODO: incorporate this into the game when initializing the players. Let the user decide how many players and its 
              # respective strategies

# Game Variables:
BUY_IN = 10
RAISE_AMT = 1


class Game:

    def __init__(self, small_blind=0, big_blind=0, raise_amounts=1, starting_card_count=2, community_card_count=5):

        # Constructor parameters
        self.players = OrderedDict()
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.raise_amounts = raise_amounts
        self.starting_card_count = starting_card_count
        self.community_card_count = community_card_count
        self.player_count = 0
        self.players_in_game = 0

        # Initialize deck
        self.deck = Deck()
        self.call = 0       # call this to remain in the game
        self.dealer = 0     # position of dealer chip
        self.pot = 0



        self.blind_count = (small_blind > 0) + (big_blind > 0)

        # Create table containing preflop odds (to be consulted by strategies)
        self.preflop_odds_table = self.create_preflop_odds_table()


    def add_player(self, player):
        """
            This function adds a players to the game
        """
        self.players[self.player_count] = player   
        self.players[self.player_count].id = self.player_count  # This gives the players a fixed numerical index (an 'I.D')

        self.player_count += 1                     # TODO: NEED TO MAKE INDEXING DYNAMIC: the way it is, if a player is in the small
                                                   # blind position or in the big blind position, it will ways stay there for every 
                                                   # round.
        self.players_in_game += 1
        

    def initializePlayerCards(self):
        """
            This function initializes player's hole cards (and the most recent actions set)
        """
        # most recent actions of all players before the current player
        self.last_player_actions = deque((self.player_count - 1) * [0], maxlen=(self.player_count - 1))

        for i in range(self.player_count):
            self.players[i].setHoleCards(self.deck.getPreFlop(
                number_of_cards=self.starting_card_count))
        return self.players


    def create_preflop_odds_table(self):
        """
            This function creates a python dictionary structure containing the probability that each possible preflop 
            hand will end-up being the best hand. This was done by using a table with precalculated odds (for speed)
            Reference: http://www.natesholdem.com/pre-flop-odds.php
            Note: 's' in the hand names means 'suited' and 'o' means 'off suit' 
        """
        preflop_odds = {}
        with open('./data/preflop_odds.txt', 'rb') as csv_file:
            reader = csv.reader(csv_file, delimiter='\t')
            for row in reader:
                preflop_odds[row[0]] = [row[1:]]

        return preflop_odds
    

    def setBlinds(self):

        if self.small_blind > 0:

            state = self.players[self.dealer + 1].states
            state[0] -= self.small_blind
            state[1] += self.small_blind
            state[2] = None

            self.pot += self.small_blind
            self.call = self.small_blind

            self.last_player_actions.append('S')

        if self.big_blind > 0:

            state = self.players[
                (self.dealer + 2) % self.player_count].states
            state[0] -= self.big_blind
            state[1] += self.big_blind
            state[2] = None

            self.pot += self.big_blind
            self.call = self.big_blind

            self.last_player_actions.append('B')

        return self.pot, self.call

    
    def placeBets(self):
       
        i = self.blind_count + 1
        cur_player_index = (self.dealer + i) % self.player_count
        cur_player = self.players[cur_player_index]
        cur_state = self.players[cur_player_index].states                                                            

        # players bet until everyone either calls or folds

        while not (cur_state[1] == self.call and (cur_state[2] == 'C' or cur_state[2] == 'R')):

            print cur_state[2], cur_state[1], self.call
            if self.players_in_game == 1:
                break

            if cur_state[2] != 'F':

                if isinstance(cur_player, Agent):
                    action = cur_player.getAction(
                        game=self,
                        call=self.call,
                        raise_amt=RAISE_AMT)                

                else:
                    action = self.players[cur_player_index].getAction(
                        player=self.players[cur_player_index],
                        game=self,
                        call=self.call,
                        raise_amt=RAISE_AMT)

                # here we could also potentially set the bet amount to 0
                if action == 'F':
                    cur_state[2] = 'F'
                    self.last_player_actions.append('F')

                if action == 'C':
                    diff = self.call - cur_state[1]

                    # your current funds must be at least the amount you bet
                    assert(cur_state[0] >= diff)

                    cur_state[0] -= diff
                    cur_state[1] += diff
                    self.pot += diff
                    cur_state[2] = 'C'
                    self.last_player_actions.append('C')

                # need to decide raising conventions
                if action == 'R':
                    # in real poker you can raise even if you haven't called (i.e. calling and raising above the call in one move)
                    diff = (self.call - cur_state[1]) + RAISE_AMT

                    cur_state[0] -= diff
                    cur_state[1] += diff
                    self.pot += diff

                    self.call += RAISE_AMT
                    cur_state[2] = 'R'
                    self.last_player_actions.append('R')

            # update recent actions to indicate player is out of game 'O' (he has folded in a previous round)
            else:
                self.last_player_actions.append('O')
                self.players_in_game -= 1




            # move to next player (array viewed as circular table)
            i += 1
            cur_player_index = (self.dealer + i) % self.player_count
            cur_player = self.players[cur_player_index]
            cur_state = self.players[cur_player_index].states

    
    def getCurrentPlayers(self):

        self.ingame_players = []

        for i in range(self.player_count):
            if self.players[i].states[2] != 'F':
                self.ingame_players.append(self.players[i].id)   # Keeps their ID stored to make it easier to identify them 
                                                                 # in the updatePlayerEarnings function

        return self.ingame_players


    def updatePlayerEarnings(self):
        # Winner 
        # we might want to update the current funds in here as well 
        # if len(self.ingame_players) == 1:
        #     self.player_list[self.ingame_players[0]][3] = self.pot
        #     self.ingame_players[0].earnings += self.pot

        winnings = (1.0 * self.pot) / len(self.ingame_players)
        # update current funds and earnings of the winners
        # also reset bet and last action
        for player_id in self.ingame_players:
            self.players[player_id].winUpdate(winnings)

        # Update the losers' states
        for player_id in range(self.player_count):
            if player_id not in self.ingame_players:
                self.players[player_id].loseUpdate()


    
    # We might want to make this a field of the Game objet instead of setting it for every player, but it prbly doesn't matter
    def showCommunityCards(self):

        community_cards = self.deck.getFlop(number_of_cards=5)

        for player_id in self.ingame_players:
            self.players[player_id].setCommunityCards(community_cards)


    # for debugging
    def printPlayerStates(self):
        for i in range(self.player_count):
            print self.players[i].states

    def playGame(self):

        self.initializePlayersStates()        
        self.setBlinds()
        self.placeBets()
        self.getCurrentPlayers()

        # Move onto post flop round
        if len(self.ingame_players) > 1:
            hand_scores = []
            self.showCommunityCards()
            
            for player in self.ingame_players:
                hand_scores.append(player.getHandScore())

            best_score = min(hand_scores)
            winners = []
            for i in xrange(len(hand_scores)):
                if hand_scores[i] == best_score:
                    winners.append(self.ingame_players[i])

            self.ingame_players = winners


        # End game
        self.updatePlayerEarnings()


    def testPlayGame(self):

        self.initializePlayerCards()
        print "Initial states :"
        print "[current funds, bet amount, action]"
        self.printPlayerStates()
        print ''
        
        self.setBlinds()
        print "After blinds :"
        print "[current funds, bet amount, action]"        
        self.printPlayerStates()
        print ''

        self.placeBets()
        print "After betting round :"
        print "[current funds, bet amount, action]"
        self.printPlayerStates()
        print ''

        self.getCurrentPlayers()
        print "Players in after betting :"
        print self.ingame_players
        print ''

        # Move onto post flop round
        if len(self.ingame_players) > 1:
            hand_scores = []
            self.showCommunityCards()       
            
            for player_id in self.ingame_players:
                hand_scores.append(self.players[player_id].getHandScore())

            best_score = min(hand_scores)
            winners = []
            for i in xrange(len(hand_scores)):
                if hand_scores[i] == best_score:
                    winners.append(self.ingame_players[i])

            self.ingame_players = winners

            print "Winners :"
            print self.ingame_players
            print ''

        # End game
        self.updatePlayerEarnings()

        print "After updating earnings :"
        print "[current funds, bet amount, action]"        
        self.printPlayerStates()
        print ''


def main(): 

    # P0 = Player(Strategy.TemperamentalProbabilisticStrategy, BUY_IN, N_PLAYERS)
    # P1 = Player(Strategy.RationalProbabilisticStrategy, BUY_IN, N_PLAYERS)
    # P2 = Player(Strategy.randomStrategy, BUY_IN, N_PLAYERS)

    n_players = 2
    P = Player(Strategy.aggresiveStrategy, BUY_IN, 2)
    A = Agent(BUY_IN, 2)


    # game = Game(small_blind=5, big_blind=10, 
    #     raise_amounts=2, starting_card_count=2)

    game = Game(small_blind=1, raise_amounts=1, starting_card_count=2)

    # game.add_player(P0)
    # game.add_player(P1)
    # game.add_player(P2)

    game.add_player(P)
    game.add_player(A)    

    for i in xrange(1000):
        game.deck = Deck()
        game.testPlayGame()

    print P.earnings
    print A.earnings

  #  game.initializePlayerCards()
  #  game.setBlinds()
  #  game.placeBets()
  #  game.getCurrentPlayers()
  #  game.updatePlayerEarnings()

  #  try:

   #     call_count = 0
   #     for i, key in enumerate(game.player_list):
   #         assert game.players[i] is key
   #         call_count += game.player_list[key][2] == 'C'

   #     assert call_count == len(game.ingame_players)

   # except AssertionError as e:
   #     raise
   # else:
   #     print "All tests passed!"

if __name__ == '__main__':
    main()



















