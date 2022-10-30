import timeit
import unittest.mock

from fastapi import Depends, FastAPI, Security, Request
from fastapi.dependencies.utils import solve_dependencies
from fastapi.testclient import TestClient

app = FastAPI()

counter_holder = {"counter": 0}


async def dep_counter():
    counter_holder["counter"] += 1
    return counter_holder["counter"]


async def super_dep(count: int = Depends(dep_counter)):
    return count


@app.get("/counter/")
async def get_counter(count: int = Depends(dep_counter)):
    return {"counter": count}


@app.get("/sub-counter/")
async def get_sub_counter(
    subcount: int = Depends(super_dep), count: int = Depends(dep_counter)
):
    return {"counter": count, "subcounter": subcount}


@app.get("/sub-counter-no-cache/")
async def get_sub_counter_no_cache(
    subcount: int = Depends(super_dep),
    count: int = Depends(dep_counter, use_cache=False),
):
    return {"counter": count, "subcounter": subcount}


@app.get("/scope-counter")
async def get_scope_counter(
    count: int = Security(dep_counter),
    scope_count_1: int = Security(dep_counter, scopes=["scope"]),
    scope_count_2: int = Security(dep_counter, scopes=["scope"]),
):
    return {
        "counter": count,
        "scope_counter_1": scope_count_1,
        "scope_counter_2": scope_count_2,
    }


# a deeper and broader dependency hierarchy:
async def dep_a(count: int = Depends(dep_counter)):
    return {"a": count}


async def dep_b(count: int = Depends(dep_counter)):
    return {"b": count}


async def dep_c(count: int = Depends(dep_counter)):
    return {"b": count}


async def dep_aa(
    a: dict = Depends(dep_a), b: dict = Depends(dep_b), c: dict = Depends(dep_c)
):
    result = {}
    result.update(a)
    result.update(b)
    result.update(c)
    return {"aa": result}


async def dep_bb(
    a: dict = Depends(dep_a), b: dict = Depends(dep_b), c: dict = Depends(dep_c)
):
    result = {}
    result.update(a)
    result.update(b)
    result.update(c)
    return {"bb": result}


async def dep_cc(
    a: dict = Depends(dep_a), b: dict = Depends(dep_b), c: dict = Depends(dep_c)
):
    result = {}
    result.update(a)
    result.update(b)
    result.update(c)
    return {"cc": result}


@app.get("/depend-cache-deep")
async def get_depend_cache_deep(
    aa: dict = Depends(dep_aa),
    bb: dict = Depends(dep_bb),
    cc: dict = Depends(dep_cc),
    count: int = Security(dep_counter),
    scope_count_1: int = Security(dep_counter, scopes=["scope"]),
    scope_count_2: int = Security(dep_counter, scopes=["scope"]),
):
    return {
        "aa": aa,
        "bb": bb,
        "cc": cc,
        "scope_counter_1": scope_count_1,
        "scope_counter_2": scope_count_2,
    }

@app.get("/depend_cache_request")
async def get_depend_cache_request(request:Request):
    return {}

client = TestClient(app)


def test_normal_counter():
    counter_holder["counter"] = 0
    response = client.get("/counter/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 1}
    response = client.get("/counter/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 2}


def test_sub_counter():
    counter_holder["counter"] = 0
    response = client.get("/sub-counter/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 1, "subcounter": 1}
    response = client.get("/sub-counter/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 2, "subcounter": 2}


def test_sub_counter_no_cache():
    counter_holder["counter"] = 0
    response = client.get("/sub-counter-no-cache/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 2, "subcounter": 1}
    response = client.get("/sub-counter-no-cache/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 4, "subcounter": 3}


def test_security_cache():
    counter_holder["counter"] = 0
    response = client.get("/scope-counter/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 1, "scope_counter_1": 2, "scope_counter_2": 2}
    response = client.get("/scope-counter/")
    assert response.status_code == 200, response.text
    assert response.json() == {"counter": 3, "scope_counter_1": 4, "scope_counter_2": 4}


def test_deep_cache(capsys):
    counter_holder["counter"] = 0
    my_counter = 0

    async def wrapper(*args, **kwargs):
        nonlocal my_counter
        my_counter += 1
        return await solve_dependencies(*args, **kwargs)

    with unittest.mock.patch("fastapi.dependencies.utils.solve_dependencies", wrapper):
        response = client.get("/depend-cache-deep/")
    assert my_counter == 8
    assert response.json() == {
        "aa": {"aa": {"a": 1, "b": 1}},
        "bb": {"bb": {"a": 1, "b": 1}},
        "cc": {"cc": {"a": 1, "b": 1}},
        "scope_counter_1": 2,
        "scope_counter_2": 2,
    }
    if False:  # pragma: no cover
        with capsys.disabled():
            print(repr(response.json()))

from fastapi.dependencies.utils import get_dependant, solve_dependencies
from fastapi import Request

def test_deep_cache_perf(capsys):
    """
    A test that can be used to test the performace of the dependency cache
    """
    if True:  # pragma: no cover
        counter_holder["counter"] = 0
        with capsys.disabled():
            call = lambda: client.get("/depend-cache-deep/")
            time_call(call, "deep cache client requests")
            
            call = get_endpoint_call(get_depend_cache_deep)
            time_call(call, "deep cache direct solve")

            call = get_endpoint_call(get_depend_cache_request)    
            time_call(call, "request direct solve")

def get_endpoint_call_new(call, path="/foo"):
    # create a dependency and call it directly
    from fastapi.dependencies.utils import DependencySolverContext
    dep = get_dependant(path="/foo", call=call)
    def solve():
        request = Request(scope={"type":"http"})
        ctx = DependencySolverContext(request=request)
        future = solve_dependencies(context=ctx, dependant=dep)
        try:
            future.send(None)
        except StopIteration:
            pass
    return solve

def get_endpoint_call_old(call, path="/foo"):
    # create a dependency and call it directly
    dep = get_dependant(path="/foo", call=call)
    def solve():
        request = Request(scope={"type":"http", "query_string": "", "headers":[]})
        future = solve_dependencies(request=request, dependant=dep)
        try:
            future.send(None)
        except StopIteration:
            pass
    return solve

import fastapi.dependencies.utils
if hasattr(fastapi.dependencies.utils, "DependencySolverContext"):
    get_endpoint_call = get_endpoint_call_new
else:
    get_endpoint_call = get_endpoint_call_old
            
def time_call(call, what):
    timer = timeit.Timer(call)
    n, t = timer.autorange()
    tpr = t / n
    rps = n / t
    print(what)
    print(f"did {n} calls in {t} seconds")
    print(f"time per call: {tpr*1000:.2f}ms, rate: {rps:.2f}/s")
