from PlanetWars import PlanetWars
import sys
import traceback

class BotModule(object):

    def planetsByDistance(self, planet, planetGroup):
        return sorted(planetGroup,
                      key=lambda oplanet: self.pwobj.Distance(planet.PlanetID(),
                                                              oplanet.PlanetID()))

    def avgDistanceFromMyPlanets(self, planet):
        dists = []
        for ePlanet in self.pwobj.MyPlanets():
            dists.append(self.pwobj.Distance(ePlanet.PlanetID(), planet))
        if len(dists) > 0:
            return sum(dists)/len(dists)
        return 0

    def planetsByStrength(self, planetGroup):
        return sorted(planetGroup,
                      key=lambda oplanet: oplanet.NumShips())

    def planetsByValue(self, planetGroup):
        pv = sorted(planetGroup,
                      key=lambda oplanet: oplanet.GrowthRate())
        pv.reverse()
        return pv

    def maxPlanetDistance(self):
        maxDistance = 0
        for oPlanet in self.pwobj.Planets():
            for iPlanet in self.pwobj.Planets():
                dist = self.pwobj.Distance(iPlanet.PlanetID(),
                                           oPlanet.PlanetID())
                if dist > maxDistance:
                    maxDistance = dist
        return maxDistance

    def shipsInRoute(self, planetobj):
        enemy_ships = 0
        my_ships = 0
        for eFleet in self.pwobj.EnemyFleets():
            if eFleet.DestinationPlanet() == planetobj.PlanetID():
                enemy_ships += eFleet.NumShips()
                break
        for eFleet in self.pwobj.MyFleets():
            if eFleet.DestinationPlanet() == planetobj.PlanetID():
                my_ships += eFleet.NumShips()
        return enemy_ships - my_ships

    def planetsUnderAttack(self):
        planets = {}
        for eFleet in self.pwobj.EnemyFleets():
            targetPlanet = eFleet.DestinationPlanet()
            if self.pwobj.GetPlanet(targetPlanet).Owner() == 1:
                if targetPlanet not in planets:
                    planets[targetPlanet] = [eFleet.NumShips(),
                                             eFleet.TurnsRemaining()]
                else:
                    planets[targetPlanet][0] += eFleet.NumShips()
                    if planets[targetPlanet][1] > eFleet.TurnsRemaining():
                        planets[targetPlanet][1] = eFleet.TurnsRemaining()
        return planets

    def numMyShipsArrivedBy(self, planet, turns):
        nships = 0
        for eFleet in self.pwobj.MyFleets():
            if eFleet.DestinationPlanet() == planet and eFleet.TurnsRemaining() < turns:
                nships += eFleet.NumShips()
        return nships

    def planetsToDefend(self):
        atPlanets = self.planetsUnderAttack()
        planetsNeedingHelp = []
        for myPlanet in atPlanets:
            myPlanetObj = self.pwobj.GetPlanet(myPlanet)
            combatDifferential = (myPlanetObj.NumShips() + \
                                      (myPlanetObj.GrowthRate() * \
                                           atPlanets[myPlanet][1])) - atPlanets[myPlanet][0]
            combatDifferential += self.numMyShipsArrivedBy(myPlanet, atPlanets[myPlanet][1])
            planetsNeedingHelp.append((myPlanet,
                                       combatDifferential,
                                       atPlanets[myPlanet][1],
                                       self.pwobj.GetPlanet(myPlanet).GrowthRate(),
                                       atPlanets[myPlanet][0]))
        # return planets sorted by growth rate
        planetsNeedingHelp.sort(cmp=lambda x,y: y[3]-x[3])
        return planetsNeedingHelp

    def scoreDifferential(self):
        myShips = 0
        theirShips = 0
        mplanets = self.pwobj.MyPlanets()
        tplanets = self.pwobj.EnemyPlanets()
        for pl in mplanets:
            myShips += pl.NumShips()
        for fl in self.pwobj.MyFleets():
            myShips += fl.NumShips()
        for pl in tplanets:
            theirShips += pl.NumShips()
        for fl in self.pwobj.EnemyFleets():
            theirShips += fl.NumShips()
        return ((myShips, theirShips),
                (len(mplanets), len(tplanets)))
    

class BravoBotModule(BotModule):

    def showArmament(self):
        self.log.write("Total Forces: %s, defense Forces: %s, offense Forces: %s\n" \
                           % (str(self.available_ships),
                              str(self.defense_ships),
                              str(self.combat_ships)))
        self.log.flush()

    def decideMode(self, scorediff):
        scores, planets = scorediff
        # Out of ships, prevent divide by zero
        if scores[0] > 0:
            self.aggression = int(round((1 - (float(scores[1]) / float(scores[0]))) * 10))
        else:
            self.aggression = -10

    def costBenefit(self, planetobj):
        er_diff = self.shipsInRoute(planetobj)
        avgDist = self.avgDistanceFromMyPlanets(planetobj.PlanetID())
        if planetobj in self.pwobj.EnemyPlanets():
            cost = (planetobj.GrowthRate() * avgDist) + planetobj.NumShips()
            cost += er_diff
        elif planetobj in self.pwobj.NeutralPlanets():
            cost = planetobj.NumShips() + er_diff

        nShips = planetobj.GrowthRate() * (self.maxDist - avgDist)
        return nShips - cost

    def costBenefitSort(self, planetGroup):
        pv = sorted(planetGroup,
                    key=lambda oplanet: self.costBenefit(oplanet))
        pv.reverse()
        return pv

    def pickTargets(self):
        if self.aggression <= 0:
            strongPlanets = self.costBenefitSort(self.pwobj.NotMyPlanets())
            planetsActual = strongPlanets
        elif self.aggression > 0:
            strongPlanets = self.pwobj.EnemyPlanets()
            sortedStrongPlanets = []
            for planet in strongPlanets:
                sortedStrongPlanets.append((self.avgDistanceFromMyPlanets(planet.PlanetID()),
                                            planet))
            sortedStrongPlanets.sort()
            planetsActual = [x[1] for x in sortedStrongPlanets]
        return planetsActual

    def commitShips(self):
        if self.aggression > 2:
            actualPerc = 0.9
            defensePerc = 0.2
        else:
            actualPerc = 0.9
            defensePerc = 0.5

        planets = {}
        self.available_ships = 0
        for ePlanet in self.pwobj.MyPlanets():
            baseShips = int(ePlanet.NumShips() * actualPerc)
            for pl in self.attackedPlanets:
                if ePlanet.PlanetID() == pl[0]:
                    if pl[1] > 0:
                        #shit, pl[1] is at the time of arrival
                        if pl[4] < ePlanet.NumShips():
                            baseShips = ePlanet.NumShips() - pl[4]
                        else:
                            baseShips = 0
                    else:
                        baseShips = 0
                    break
            if baseShips > 0:
                planets[ePlanet.PlanetID()] = baseShips
                self.available_ships += baseShips
        self.defense_ships = int(self.available_ships * defensePerc)
        self.combat_ships = self.available_ships - self.defense_ships
        self.showArmament()
        return planets

    def issueOrders(self):
        for planet in self.attackedPlanets:
            if planet[1] >= 0:
                continue
            planetid = planet[0]
            neededships = abs(planet[1]) + 1
            for oplanet in self.planetsByDistance(self.pwobj.GetPlanet(planetid),
                                                  self.pwobj.MyPlanets()):
                if neededships < 1:
                    break
                oplanetid = oplanet.PlanetID()
                if oplanetid in self.committedPlanets:
                    canCommit = self.committedPlanets[oplanetid]
                    if canCommit >= self.defense_ships:
                        canCommit = self.defense_ships
                    if canCommit >= neededships:
                        canCommit = neededships
                    if canCommit < 1:
                        continue
                    neededships -= canCommit
                    self.available_ships -= canCommit
                    self.defense_ships -= canCommit
                    self.log.write("Defense can commit %s of %s from %s to %s\n" % (canCommit,
                                                self.committedPlanets[oplanetid],
                                                                      oplanetid,
                                                                      planetid))
                    self.log.flush()
                    self.committedPlanets[oplanetid] -= canCommit
                    # Issue Defense Order
                    self.pwobj.IssueOrder(oplanetid, planetid, canCommit)
        self.showArmament()
        for planet in self.chosenTargets:
            planetobj = planet
            planetid = planetobj.PlanetID()
            neededships = planetobj.NumShips() + 1
            for oplanet in self.planetsByDistance(planetobj, self.pwobj.MyPlanets()):
                if neededships < 1:
                    break
                oplanetid = oplanet.PlanetID()
                if oplanetid in self.committedPlanets:
                    canCommit = self.committedPlanets[oplanetid]
#                   if canCommit >= self.combat_ships
#                       canCommit = self.combat_ships
                    if canCommit >= neededships:
                        canCommit = neededships
                    if canCommit < 1:
                        continue
                    neededships -= canCommit
                    self.available_ships -= canCommit
                    self.combat_ships -= canCommit
                    self.log.write("Offense an commit %s of %s from %s to %s\n" % (canCommit,
                                                self.committedPlanets[oplanetid],
                                                                      oplanetid,
                                                                      planetid))
                    self.log.flush()
                    self.committedPlanets[oplanetid] -= canCommit
                    # Issue Offense Order
                    self.pwobj.IssueOrder(oplanetid, planetid, canCommit)
        self.showArmament()

    def run(self, pwobj, log):
        log.write("Starting BetaBot\n")
        self.log = log
        self.pwobj = pwobj
        self.maxDist = self.maxPlanetDistance()

        self.attackedPlanets = self.planetsToDefend()
        self.decideMode(self.scoreDifferential())
        self.committedPlanets = self.commitShips()
        self.chosenTargets = self.pickTargets()
        self.issueOrders()
            
class AggressiveBotModule(BotModule):

    def run(self, pwobj, log):
        log.write("starting ABM")
        self.pwobj = pwobj
        for myPlanet in self.planetsByStrength(pwobj.MyPlanets()):
            attackSize = int(myPlanet.NumShips() * 0.5)
            if len(pwobj.MyPlanets()) > len(pwobj.EnemyPlanets()):
                targetPlanets = pwobj.EnemyPlanets()
            else:
                targetPlanets = pwobj.NotMyPlanets()
            for nearPlanet in self.planetsByDistance(myPlanet, targetPlanets):
                if nearPlanet.NumShips()+1 <= attackSize:
                    attackSize = attackSize - nearPlanet.NumShips()+1
                    pwobj.IssueOrder(myPlanet.PlanetID(),
                                     nearPlanet.PlanetID(),
                                     nearPlanet.NumShips()+1)


def main():
    map_data = ''
    bot = BravoBotModule()
    log = open("bbot.log","w")
    while True:
        current_line = raw_input()
        if len(current_line) >= 2 and current_line.startswith("go"):
            pw = PlanetWars(map_data)
            bot.run(pw, log)
            pw.FinishTurn()
            map_data = ''
        else:
            map_data += current_line + '\n'
    log.close()

if __name__ == '__main__':
  try:
    import psyco
    psyco.full()
  except ImportError:
    pass
  try:
      log = open("bbloop.log","w")
      main()
  except KeyboardInterrupt:
      print 'ctrl-c, leaving ...'
  except Exception, e:
      log.write(traceback.format_exc())
