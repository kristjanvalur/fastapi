import timeit
import unittest.mock

from fastapi import Depends, FastAPI, Security
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
def dep_a(count: int = Depends(dep_counter)):
    return {"a": count}


def dep_b(count: int = Depends(dep_counter)):
    return {"b": count}


def dep_c(count: int = Depends(dep_counter)):
    return {"b": count}


def dep_aa(
    a: dict = Depends(dep_a), b: dict = Depends(dep_b), c: dict = Depends(dep_c)
):
    result = {}
    result.update(a)
    result.update(b)
    result.update(c)
    return {"aa": result}


def dep_bb(
    a: dict = Depends(dep_a), b: dict = Depends(dep_b), c: dict = Depends(dep_c)
):
    result = {}
    result.update(a)
    result.update(b)
    result.update(c)
    return {"bb": result}


def dep_cc(
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
    if False:
        with capsys.disabled():
            print(repr(response.json()))


def test_deep_cache_perf(capsys):
    """
    A test that can be used to test the performace of the dependency cache
    """
    return
    counter_holder["counter"] = 0
    with capsys.disabled():
        timer = timeit.Timer(lambda: client.get("/depend-cache-deep/"))
        n, t = timer.autorange()
        tpr = t / n
        rps = n / t

        print(f"did {n} requests in {t} seconds")
        print(f"time per request: {tpr*1000:.2f}ms, rate: {rps:.2f}/s")
