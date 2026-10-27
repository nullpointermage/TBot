// Account-free characterization of the pinned Go model surface.
package main

import (
	"encoding/json"
	"fmt"
	o "github.com/alaingilbert/ogame/pkg/ogame"
	s "github.com/alaingilbert/ogame/pkg/simulator"
	u "github.com/alaingilbert/ogame/pkg/utils"
	"math"
	"reflect"
	"time"
)

var assertions int

func check(name string, got, want any) {
	assertions++
	if !reflect.DeepEqual(got, want) {
		panic(fmt.Sprintf("%s: got %#v want %#v", name, got, want))
	}
	fmt.Printf("PASS %s = %#v\n", name, got)
}
func wire(v any) map[string]any {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	var m map[string]any
	if err = json.Unmarshal(b, &m); err != nil {
		panic(err)
	}
	return m
}
func main() {
	check("resource-add-drops-energy", o.Resources{Energy: 9, Food: 4}.Add(o.Resources{}), o.Resources{})
	check("resource-subpercent-drops-population", o.Resources{Metal: 7, Energy: 9, Population: 12}.SubPercent(.5), o.Resources{Metal: 4, Energy: 5})
	check("afford-ignores-energy", o.Resources{}.CanAfford(o.Resources{Energy: 900000}), true)
	check("free-price-div-maxint", o.Resources{}.Div(o.Resources{}), int64(math.MaxInt))
	check("zero-probe-capacity-fitsin-zero", o.Resources{Metal: 100}.FitsIn(o.EspionageProbe, o.Researches{}, o.LfBonuses{}, o.NoClass, .05, false), int64(0))
	check("storage-floating-exponent-level1", o.MetalStorage.Capacity(1), int64(20000))
	check("graviton-factor-three-level2", o.GravitonTechnology.GetPrice(2, o.LfBonuses{}).Energy, int64(900000))
	check("deut-price-truncates-level2", o.DeuteriumSynthesizer.GetPrice(2, o.LfBonuses{}), o.Resources{Metal: 337, Crystal: 112})
	check("generic-level-zero-not-rejected", o.MetalMine.GetPrice(0, o.LfBonuses{}), o.Resources{Metal: 40, Crystal: 10})
	b := o.LfBonuses{CostTimeBonuses: o.CostTimeBonuses{o.ResidentialSectorID: {Cost: .5}}}
	check("lf-building-ignores-cost-map", o.ResidentialSector.GetPrice(2, b), o.Resources{Metal: 16, Crystal: 4})
	check("lf-building-energy-exponent-Lminus1", o.BiosphereFarm.GetPrice(2, o.LfBonuses{}).Energy, int64(16))
	b.PlanetLfResearchCostTimeBonus = o.CostTimeBonus{Duration: .5}
	check("lf-research-ignores-planet-duration", o.IntergalacticEnvoys.ConstructionTime(2, 8, o.Facilities{ResearchLab: 30}, b, o.Discoverer, true), 360*time.Second)
	b.CostTimeBonuses[o.IntergalacticEnvoysID] = o.CostTimeBonus{Duration: .5}
	check("lf-research-per-id-duration", o.IntergalacticEnvoys.ConstructionTime(2, 8, o.Facilities{}, b, o.NoClass, false), 180*time.Second)
	b.CostTimeBonuses[o.SolarPlantID] = o.CostTimeBonus{Duration: .25}
	check("duration-discount-after-minimum", o.SolarPlant.ConstructionTime(1, 6, o.Facilities{RoboticsFactory: 10, NaniteFactory: 7}, b, o.NoClass, false), 750*time.Millisecond)
	check("duration-wire-nanoseconds", wire(o.Construction{Countdown: 2 * time.Second})["Countdown"], float64(2000000000))
	check("general-pathfinder-no-cargo-bonus", o.Pathfinder.GetCargoCapacity(o.Researches{}, o.LfBonuses{}, o.General, .05, false), int64(10000))
	b.LfShipBonuses = o.LfShipBonuses{o.LargeCargoID: {FuelConsumption: .1}}
	check("fuel-lf-added-before-general-base-half", o.LargeCargo.GetFuelConsumption(o.Researches{}, b, o.General, 1), int64(30))
	check("general-deathstar-speed-excluded", o.Deathstar.GetSpeed(o.Researches{}, o.LfBonuses{}, o.General, o.NoAllianceClass), int64(100))
	check("empty-fleet-slowest-maxint64", o.ShipsInfos{}.Speed(o.Researches{}, o.LfBonuses{}, o.NoClass, o.NoAllianceClass), int64(math.MaxInt64))
	fleet := o.ShipsInfos{SmallCargo: 2}
	copyPtr := fleet.ToPtr()
	copyPtr.SmallCargo = 8
	check("ships-toptr-is-copy", fleet.SmallCargo, int64(2))
	fleet.Add(o.ShipsInfos{SmallCargo: -1})
	check("ships-add-sendall-sentinel", fleet.SmallCargo, int64(-1))
	check("sentinel-ignored-by-count", fleet.CountShips(), int64(0))
	check("has-negative-request-unconstrained", o.ShipsInfos{}.Has(o.ShipsInfos{SmallCargo: -1}), true)
	check("has-ships-includes-stationary", o.ShipsInfos{Crawler: 1}.HasShips(), true)
	check("has-flyable-excludes-stationary", o.ShipsInfos{Crawler: 1}.HasFlyableShips(), false)
	report := o.EspionageReport{HasFleetInformation: true, HasDefensesInformation: true}
	check("report-section-flags-collapse-nil-counts", report.IsDefenceless(), true)
	report.SmallShieldDome = u.Ptr(int64(1))
	check("report-domes-not-blocking", report.IsDefenceless(), true)
	report.SolarSatellite = u.Ptr(int64(1))
	check("report-satellite-blocks", report.IsDefenceless(), false)
	check("overfull-slots-not-equality", (o.Slots{InUse: 3, Total: 2}).IsAllSlotsInUse(o.Attack), false)
	check("zero-slots-block", (o.Slots{}).IsAllSlotsInUse(o.Attack), true)
	check("zero-fleet-cancellable-predicate", (o.Fleet{}).IsCancellable(), true)
	check("temperature-negative-half-away", (o.Temperature{Min: -2, Max: -1}).Mean(), int64(-2))
	_, err := o.ParseCoord("[999:999:999")
	check("unbalanced-coordinate-bracket-accepted", err, nil)
	check("do-parse-error-zero", o.DoParseCoord("bad"), o.Coordinate{})
	check("unknown-id-negative-set", o.ID(-1).IsSet(), true)
	check("negative-fleet-id-not-set", o.FleetID(-1).IsSet(), false)
	check("id-string-not-json-number", wire(struct{ ID o.ID }{o.MetalMineID})["ID"], float64(1))
	sys := o.SystemInfos{}
	sys.SetGalaxy(2)
	sys.SetSystem(3)
	sys.Events.Darkmatter = 12
	sys.OverlayToken = "fixture"
	m := wire(sys)
	_, present := m["Events"]
	check("system-events-omitted", present, false)
	_, present = m["Relocations"]
	check("system-relocations-omitted", present, false)
	_, present = m["OverlayToken"]
	check("system-token-omitted", present, false)
	raw, _ := json.Marshal(sys)
	var decoded o.SystemInfos
	if err = json.Unmarshal(raw, &decoded); err != nil {
		panic(err)
	}
	check("system-no-private-roundtrip", decoded.Galaxy(), int64(0))
	techs := o.Techs{ResourcesBuildings: o.ResourcesBuildings{SolarSatellite: 3}, ShipsInfos: o.ShipsInfos{SolarSatellite: 4}}
	_, present = wire(techs)["SolarSatellite"]
	check("techs-ambiguous-satellite-omitted", present, false)
	lf := o.LfResearches{IntergalacticEnvoys: u.Ptr(int64(1))}
	lazy := lf.Lazy()
	*lazy.GetIntergalacticEnvoys() = 7
	check("lf-getter-pointee-alias", *lf.IntergalacticEnvoys, int64(7))
	lf.IntergalacticEnvoys = u.Ptr(int64(9))
	check("lf-lazy-old-pointer-snapshot", *lazy.GetIntergalacticEnvoys(), int64(7))
	slots := o.LfResearchDetails{}
	slots.Slots[0] = o.LfSlot{Allowed: true, Locked: true}
	check("lf-available-slot-ignores-locked", slots.AvailableSlot(), int64(1))
	check("roundthousandth-is-floor", u.RoundThousandth(-1.2341), -1.235)
	vals := []int{1, 2}
	p := u.Find(vals, func(n int) bool { return n == 2 })
	*p = 8
	check("find-pointer-is-copy", vals[1], 2)
	params := s.SimulatorParams{Simulations: 1, FleetToDebris: .3}
	result := s.Simulate(s.Attacker{ShipsInfos: o.ShipsInfos{Reaper: 1}}, s.Defender{}, params)
	check("simulator-reaper-attacker-ignored", result.Draw, 100)
	result = s.Simulate(s.Attacker{ShipsInfos: o.ShipsInfos{LargeCargo: 1}}, s.Defender{ShipsInfos: o.ShipsInfos{Reaper: 1}}, params)
	check("simulator-reaper-defender-ignored", result.AttackerWin, 100)
	check("simulator-forced-empty-logs", result.Logs, "")
	fmt.Printf("ALL %d CHARACTERIZATIONS PASSED\n", assertions)
}
