// Offline characterization of the pinned, unmodified Go library.
// All HTTP clients are in-memory fakes; no device Build, account or socket is used.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/alaingilbert/ogame/pkg/device"
	"github.com/alaingilbert/ogame/pkg/gameforge"
	"github.com/alaingilbert/ogame/pkg/gameforge/solvers"
	"github.com/alaingilbert/ogame/pkg/httpclient"
	"github.com/alaingilbert/ogame/pkg/taskRunner"
	"github.com/urfave/cli/v3"
)

type memoryTransport struct {
	body     string
	status   int
	requests int
}

func (m *memoryTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	m.requests++
	return &http.Response{StatusCode: m.status, Header: make(http.Header),
		Body: io.NopCloser(strings.NewReader(m.body)), Request: req}, nil
}

type memoryDevice struct {
	loginBody string
	requests  int
}

func (d *memoryDevice) GetBlackbox() (string, error) { return "fixture", nil }
func (d *memoryDevice) Do(req *http.Request) (*http.Response, error) {
	d.requests++
	var body string
	var status int
	switch req.URL.Path {
	case "/config/configuration.js":
		body = `{"gameEnvironmentId":"fixture","platformGameId":"fixture"}`
		status = http.StatusOK
	case "/api/v2/authProviders/mauth/sessions":
		body = d.loginBody
		status = http.StatusCreated
	default:
		panic("unexpected request: in-memory fake refuses any real request")
	}
	return &http.Response{StatusCode: status, Header: make(http.Header),
		Body: io.NopCloser(strings.NewReader(body)), Request: req}, nil
}

type memoryTask struct{ done chan struct{} }

func (m *memoryTask) SetTaskDoneCh(ch chan struct{}) { m.done = ch }

func panics(fn func()) (out bool) {
	defer func() {
		if recover() != nil {
			out = true
		}
	}()
	fn()
	return false
}

func main() {
	tlsRead := false
	tlsInput := ""
	cliCmd := &cli.Command{
		Flags: []cli.Flag{&cli.StringFlag{Name: "enable-tls", Value: "false"}},
		Action: func(ctx context.Context, cmd *cli.Command) error {
			tlsRead = cmd.Bool("enable-tls")
			tlsInput = cmd.String("enable-tls")
			return nil
		},
	}
	cliErr := cliCmd.Run(context.Background(), []string{"offline-fixture", "--enable-tls=true"})
	count := 0
	check := func(name string, passed bool) {
		if !passed {
			panic("FAIL: " + name)
		}
		count++
		fmt.Println("PASS:", name)
	}
	check("StringFlag true read as Bool returns false", cliErr == nil && tlsInput == "true" && !tlsRead)
	check("empty fingerprint array panics", panics(func() { _, _ = device.ParseBlackbox("[]") }))
	check("short version12 fingerprint panics", panics(func() { _, _ = device.ParseBlackbox("[12]") }))
	check("empty blackbox encryption panics", panics(func() { _ = device.EncryptBlackbox("") }))
	check("empty blackbox decryption panics", panics(func() { _, _ = device.DecryptBlackbox("") }))
	by, err := json.Marshal(&device.JsFingerprint{ConstantVersion: 8})
	if err != nil {
		panic(err)
	}
	_, err = device.ParseBlackbox(string(by))
	check("version8 marshaler output is not accepted by its parser", err != nil)

	tr := &memoryTransport{body: "[]", status: http.StatusInternalServerError}
	accounts, err := gameforge.GetUserAccounts(context.Background(), &http.Client{Transport: tr},
		gameforge.OGAME, gameforge.Lobby, "fixture")
	check("account-list JSON is accepted despite HTTP500", err == nil && len(accounts) == 0 && tr.requests == 1)
	d := &memoryDevice{loginBody: "null"}
	gf, err := gameforge.New(&gameforge.Config{Device: d, Platform: gameforge.OGAME})
	if err != nil {
		panic(err)
	}
	check("null HTTP201 login result panics", panics(func() {
		_, _ = gf.Login(&gameforge.LoginParams{Username: "fixture", Password: "fixture"})
	}) && d.requests == 2)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	created := false
	runner := taskRunner.NewTaskRunner(ctx, func() *memoryTask { created = true; return &memoryTask{} })
	task := runner.WithPriority(taskRunner.Normal)
	check("canceled task runner still returns a factory task", created && task.done != nil)
	close(task.done)

	old := &memoryTransport{body: "original", status: 200}
	temporary := &memoryTransport{body: "temporary", status: 200}
	client := &httpclient.Client{Client: &http.Client{Transport: old}}
	err = client.WithTransport(temporary, func(c *httpclient.Client) error {
		resp, e := c.Get("https://fixture.invalid/")
		if e != nil {
			return e
		}
		defer resp.Body.Close()
		body, e := io.ReadAll(resp.Body)
		if e == nil && string(body) != "temporary" {
			panic("wrong transport")
		}
		return e
	})
	check("temporary transport is used then restored", err == nil && client.Transport == old && temporary.requests == 1 && old.requests == 0)

	oldDefault := http.DefaultClient
	solverHTTP := &memoryTransport{body: `{"answer":99}`, status: 200}
	http.DefaultClient = &http.Client{Transport: solverHTTP}
	defer func() { http.DefaultClient = oldDefault }()
	answer, err := solvers.NinjaSolver("fixture")(context.Background(), []byte("fixture"), []byte("fixture"))
	check("Ninja solver does not bound returned answer", err == nil && answer == 99 && solverHTTP.requests == 1)
	fmt.Printf("%d offline Go characterizations passed; no network requests or account actions\n", count)
}
