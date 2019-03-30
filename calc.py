import requests
import json
import logging
import pprint


post = {
    "EIGENVERBRFAKT_ROOST":
        {
            "UUID": "c7f542c0-52e3-11e9-8af8-add30f3dce39",
            "VAL": None
        }, "EIGENVERBRFAKT_AREAL":
        {
            "UUID": "bc1153d0-52e3-11e9-8b12-81bb992647d4",
            "VAL": None

        }, "AUTARKIE_ROOST":
        {
            "UUID": "e456b3b0-52e3-11e9-8bac-6f4ab83bef5e",
            "VAL": None
        }, "AUTARKIE_AREAL":
        {
            "UUID": "daea7970-52e3-11e9-9a15-3dfaa6a6e36e",
            "VAL": None
        }, "DECKUNGSGRAD_ROOST":
        {
            "UUID": "ce1a5bc0-52e3-11e9-ab1e-77066e8bcf7b",
            "VAL": None
        }, "DECKUNGSGRAD_AREAL":
        {
            "UUID": "d36e2e10-52e3-11e9-b4e8-9fa3e744433e",
            "VAL": None
        }

}


vars = {
    "EIGENVERBAUCH_ROOST":
    {
        "UUID_GET": "92c86080-50c3-11e9-bedf-67c46bcd6f0f",
        "VAL": None
    }, "EIGENVERBRAUCH_AREAL":
    {
       "UUID_GET": "a6092f10-51fd-11e9-83a7-dd60cbfebfdf",
       "VAL": None
    }, "PV_PROD":
    {
       "UUID_GET": "101ca060-50a3-11e9-a591-cf9db01e4ddd",
       "VAL": None
    }, "VERBRAUCH_EFH_ROOST":
    {
        "UUID_GET": "694b4340-50a5-11e9-9c77-f52bc9d2d118",
        "VAL": None
    }, "DEFH_8B":
    {
        "UUID_GET": "1e4b1530-4fc9-11e9-b832-cf5186ec2738",
        "VAL": None
    }, "DEFH_8C":
    {
        "UUID_GET": "213946b0-4fc9-11e9-aacc-758bb6712b5f",
        "VAL": None
    }
}

VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from=-10min"

VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"


def main():
    for key, value in vars.items():
        req = requests.get(VZ_GET_URL.format(value["UUID_GET"]))
        data = json.loads(req.content)
        #pprint.pprint(data)
        value["VAL"] = data["data"]["average"]
    post["EIGENVERBRFAKT_ROOST"]["VAL"] = vars["EIGENVERBAUCH_ROOST"]["VAL"] / \
        vars["PV_PROD"]["VAL"] * 100
    post["EIGENVERBRFAKT_AREAL"]["VAL"] = vars["EIGENVERBRAUCH_AREAL"]["VAL"] / \
        vars["PV_PROD"]["VAL"] * 100
    post["AUTARKIE_ROOST"]["VAL"] = vars["EIGENVERBAUCH_ROOST"]["VAL"] / \
        vars["VERBRAUCH_EFH_ROOST"]["VAL"] * 100
    post["AUTARKIE_AREAL"]["VAL"] = vars["EIGENVERBRAUCH_AREAL"]["VAL"] / (
        vars["VERBRAUCH_EFH_ROOST"]["VAL"] + vars["DEFH_8B"]["VAL"] + vars["DEFH_8C"]["VAL"]) * 100
    post["DECKUNGSGRAD_ROOST"]["VAL"] = vars["PV_PROD"]["VAL"] / \
        vars["VERBRAUCH_EFH_ROOST"]["VAL"] * 100
    post["DECKUNGSGRAD_AREAL"]["VAL"] = vars["PV_PROD"]["VAL"] / (
        vars["VERBRAUCH_EFH_ROOST"]["VAL"] + vars["DEFH_8B"]["VAL"] + vars["DEFH_8C"]["VAL"]) * 100

    for key, value in post.items():    
        poststring = VZ_POST_URL.format(value["UUID"], value["VAL"])
        print(poststring)
        postreq = requests.post(poststring)
        print(postreq.ok)


if __name__ == "__main__":
    main()
