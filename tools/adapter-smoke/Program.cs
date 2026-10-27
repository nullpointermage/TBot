// Offline characterization of the pinned adapter, not a corrected implementation.
// All HTTP calls are intercepted in memory. Never initialize/start the daemon here.
using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using TBot.Ogame.Infrastructure;
using TBot.Ogame.Infrastructure.Enums;
using TBot.Ogame.Infrastructure.Exceptions;
using TBot.Ogame.Infrastructure.Models;

var passed = new List<string>();
void Check(bool condition, string name) {
    if (!condition) throw new Exception(name);
    passed.Add(name);
    Console.WriteLine("PASS " + name);
}

(OgameService service, StubHandler handler) Create(Func<HttpRequestMessage, HttpResponseMessage> response) {
    var handler = new StubHandler(response);
    var client = new HttpClient(handler) { BaseAddress = new Uri("http://in-memory.invalid/") };
    var service = new OgameService(null!);
    typeof(OgameService).GetField("_client", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(service, client);
    return (service, handler);
}
HttpResponseMessage Reply(HttpStatusCode status, string body) => new(status) {
    Content = new StringContent(body, Encoding.UTF8, "application/json")
};

var ip = Create(_ => throw new Exception("Unexpected transport call"));
try {
    await ip.service.GetTbotIP();
    throw new Exception("Absolute URI unexpectedly accepted as relative");
} catch (UriFormatException) {
    Check(ip.handler.Calls == 0, "GetTbotIP rejects absolute URI before transport");
}

var offer = Create(_ => Reply(HttpStatusCode.BadRequest,
    "{\"Status\":\"error\",\"Code\":400,\"Message\":\"Offer already accepted\",\"Result\":null}"));
var state = await offer.service.BuyOfferOfTheDay();
Check(state == OfferOfTheDayStatus.OfferOfTheDayUnknown && offer.handler.Calls == 1,
    "Already-accepted error envelope is classified Unknown, not AlreadyBought");

var malformed = Create(_ => Reply(HttpStatusCode.OK, "not JSON"));
Exception? malformedError = null;
try { await malformed.service.GetServerName(); }
catch (Exception error) { malformedError = error; }
Check(malformedError is not null && malformedError is not OgamedException && malformed.handler.Calls == 1,
    "Malformed HTTP 200 escapes as a non-OgamedException");
Console.WriteLine("OBSERVED malformed response exception: " + malformedError!.GetType().FullName);

var staff = Create(request => request.RequestUri!.AbsolutePath.EndsWith("has-commander")
    ? Reply(HttpStatusCode.OK, "{\"Status\":\"ok\",\"Result\":true}")
    : Reply(HttpStatusCode.BadRequest, "{\"Status\":\"error\",\"Message\":\"fixture\",\"Result\":null}"));
var staffResult = await staff.service.GetStaff();
Check(!staffResult.Commander && staff.handler.Calls == 2,
    "GetStaff discards earlier successful flags when a later lookup fails");

var envelope = Create(_ => Reply(HttpStatusCode.BadRequest,
    "{\"Status\":\"ok\",\"Result\":\"fixture-server\"}"));
Check(await envelope.service.GetServerName() == "fixture-server" && envelope.handler.Calls == 1,
    "An ok envelope can override HTTP 400 in ManageResponse");

var ships = new Ships(lightFighter: 10);
ships.Remove(Buildables.LightFighter, 2);
Check(ships.LightFighter == 10, "Ships.Remove does not subtract an affordable quantity");
var stationary = new Ships(solarSatellite: 3, crawler: 4);
Check(stationary.HasMovableFleet(), "Stationary-only ships still satisfy HasMovableFleet");
var movable = stationary.GetMovableShips();
Check(ReferenceEquals(movable, stationary) && stationary.SolarSatellite == 0 && stationary.Crawler == 0,
    "GetMovableShips mutates and returns the original inventory");
var defenses = new Defences(rocketlauncher: 5);
Check(defenses.HasAtLeast(new Defences(rocketlauncher: 10), times: 2),
    "Defences.HasAtLeast scales owned rather than requested quantities");
var report = new EspionageReport { HasFleetInformation = true, HasDefensesInformation = true };
Check(report.IsDefenceless(), "Espionage null combat fields count as defenceless with both information flags");
report.LightFighter = 0;
Check(!report.IsDefenceless(), "Explicit zero is not equivalent to null in IsDefenceless");
Check(new Resources(metal: 100).Round(100).Metal == 1000,
    "Resources.Round uses fixed 1000 multiplier even with another divisor");
Check(Coordinate.FromString("prefix 12:34:5 planet trailing").Galaxy == 2,
    "Unanchored coordinate regex can consume the trailing digit of a multi-digit galaxy");

Console.WriteLine(JsonSerializer.Serialize(new { kind = "offline-adapter-characterization", assertions = passed.Count,
    networkRequests = 0, daemonStarted = false, accountActions = false }));

sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> response) : HttpMessageHandler {
    public int Calls { get; private set; }
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token) {
        Calls++;
        return Task.FromResult(response(request));
    }
}
