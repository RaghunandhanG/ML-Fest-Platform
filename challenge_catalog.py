"""Canonical challenge metadata and GitHub resource mapping."""

CATALOG = [
    {
        "order": 1,
        "title": "Challenge-1",
        "description": "Data poisoning challenge from the Yugam ML CTF repository.",
        "category": "Data Poisoning",
        "difficulty": "Easy",
        "total_points": 2,
        "flag_points_max": 1,
        "explanation_points_max": 1,
        "resources": [
            {
                "display_name": "Gatekeeper_Challenge.ipynb",
                "local_name": "challenge1_Gatekeeper_Challenge.ipynb",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-1/Gatekeeper_Challenge.ipynb",
            },
            {
                "display_name": "gatekeeper_dataset.csv",
                "local_name": "challenge1_gatekeeper_dataset.csv",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-1/gatekeeper_dataset.csv",
            },
        ],
        "flags": [
            {"flag_content": "CTF{p01s0n_th3_w3ll_g4t3_f4lls}", "flag_order": 1, "points_value": 2, "description": "Final verification flag"},
        ],
    },
    {
        "order": 2,
        "title": "Challenge-2",
        "description": "Constrained data poisoning challenge from the Yugam ML CTF repository.",
        "category": "Data Poisoning",
        "difficulty": "Medium",
        "total_points": 3,
        "flag_points_max": 1,
        "explanation_points_max": 2,
        "resources": [
            {
                "display_name": "Gatekeeper_Challenge-2.ipynb",
                "local_name": "challenge2_Gatekeeper_Challenge-2.ipynb",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-2/Gatekeeper_Challenge-2.ipynb",
            },
            {
                "display_name": "gatekeeper_dataset.csv",
                "local_name": "challenge2_gatekeeper_dataset.csv",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-2/gatekeeper_dataset.csv",
            },
        ],
        "flags": [
            {"flag_content": "CTF{sh4d0ws_sl1p_p4st_th3_l0ck3d_g4t3}", "flag_order": 1, "points_value": 3, "description": "Final verification flag"},
        ],
    },
    {
        "order": 3,
        "title": "Challenge-3",
        "description": "Model repair challenge from the Yugam ML CTF repository.",
        "category": "Model Security",
        "difficulty": "Hard",
        "total_points": 4,
        "flag_points_max": 2,
        "explanation_points_max": 2,
        "resources": [
            {
                "display_name": "Gatkeepr_Challenge-3.ipynb",
                "local_name": "challenge3_Gatkeepr_Challenge-3.ipynb",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-3/Gatkeepr_Challenge-3.ipynb",
            },
            {
                "display_name": "gatekeeper_dataset.csv",
                "local_name": "challenge3_gatekeeper_dataset.csv",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-3/gatekeeper_dataset.csv",
            },
            {
                "display_name": "tampered_model.pkl",
                "local_name": "challenge3_tampered_model.pkl",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-3/tampered_model.pkl",
            },
        ],
        "flags": [
            {"flag_content": "CTF{r3wr1t3_th3_m1nd_r3cl41m_th3_g4t3}", "flag_order": 1, "points_value": 4, "description": "Final verification flag"},
        ],
    },
    {
        "order": 4,
        "title": "Challenge-4",
        "description": "Evaluation challenge from the Yugam ML CTF repository.",
        "category": "Model Evaluation",
        "difficulty": "Expert",
        "total_points": 3,
        "flag_points_max": 2,
        "explanation_points_max": 1,
        "resources": [
            {
                "display_name": "The_Model_That_Refused_To_Learn.ipynb",
                "local_name": "challenge4_The_Model_That_Refused_To_Learn.ipynb",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-4/The_Model_That_Refused_To_Learn.ipynb",
            },
            {
                "display_name": "bank.csv",
                "local_name": "challenge4_bank.csv",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-4/bank.csv",
            },
        ],
        "flags": [
            {"flag_content": "CTF{4w4k3n_th3_sl33p1ng_s3nt1n3l}", "flag_order": 1, "points_value": 3, "description": "Final verification flag"},
        ],
    },
    {
        "order": 5,
        "title": "Challenge-5",
        "description": "Weight recovery challenge \u2014 find the exact model weights that produce a perfect fit.",
        "category": "Model Analysis",
        "difficulty": "Medium",
        "total_points": 3,
        "flag_points_max": 2,
        "explanation_points_max": 1,
        "resources": [
            {
                "display_name": "The_Weight_of_Truth.ipynb",
                "local_name": "challenge5_The_Weight_of_Truth.ipynb",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-5/The_Weight_of_Truth.ipynb",
            },
            {
                "display_name": "dataset.csv",
                "local_name": "challenge5_dataset.csv",
                "url": "https://raw.githubusercontent.com/RaghunandhanG/Yugam_ML_Challenge-3/main/Challenge-5/dataset.csv",
            },
        ],
        "flags": [
            {"flag_content": "CTF{w31ght_0f_truth_r3v34l3d}", "flag_order": 1, "points_value": 3, "description": "Final verification flag"},
        ],
    },
]


def get_catalog_by_order():
    return {item["order"]: item for item in CATALOG}


def get_resources_by_order():
    return {item["order"]: item["resources"] for item in CATALOG}
