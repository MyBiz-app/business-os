// Generated from catalog/*.json by `pnpm verticals:export`. Do not edit by hand.
import type { Entry } from "./index";

export const CATALOG: Entry[] = [
  {
    "key": "fitness",
    "order": 1,
    "status": "live",
    "icon": "dumbbell",
    "color": "from-indigo-500 to-violet-500",
    "terms": "fitness",
    "client_term": "member",
    "booking_modes": [
      "class",
      "appointment"
    ],
    "cancellation_window_minutes": 120,
    "booking_requires_plan": true,
    "health_form": "fitness",
    "default_preset": "growing",
    "recommended_modules": [
      "client_app"
    ],
    "client_fields": [
      {
        "key": "goal",
        "kind": "select",
        "options": [
          "weight_loss",
          "strength",
          "flexibility",
          "rehab",
          "general"
        ]
      },
      {
        "key": "injuries",
        "kind": "long_text",
        "max_length": 1000
      }
    ],
    "default_plans": [
      {
        "names": {
          "he": "מנוי חודשי ללא הגבלה",
          "en": "Monthly unlimited"
        },
        "kind": "membership",
        "validity_days": 30,
        "prices": {
          "ILS": 45000,
          "USD": 12900,
          "EUR": 11900
        }
      },
      {
        "names": {
          "he": "כרטיסייה 10 כניסות",
          "en": "10-class card"
        },
        "kind": "punch_card",
        "validity_days": 120,
        "credits": 10,
        "prices": {
          "ILS": 60000,
          "USD": 18000,
          "EUR": 16000
        }
      },
      {
        "names": {
          "he": "כניסה בודדת",
          "en": "Single class"
        },
        "kind": "punch_card",
        "validity_days": 30,
        "credits": 1,
        "prices": {
          "ILS": 7000,
          "USD": 2000,
          "EUR": 1800
        }
      }
    ],
    "children": [
      {
        "key": "gym",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "אימון אישי",
              "en": "Personal training"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 25000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "הערכת כושר והתאמת תוכנית",
              "en": "Fitness assessment"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 15000
            },
            "color": "#10b981"
          }
        ]
      },
      {
        "key": "pilates",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "פילאטיס מזרן",
              "en": "Mat pilates"
            },
            "duration_minutes": 55,
            "booking_mode": "class",
            "capacity": 12,
            "prices": {
              "ILS": 7000
            },
            "color": "#8b5cf6"
          },
          {
            "names": {
              "he": "פילאטיס מכשירים (רפורמר)",
              "en": "Reformer pilates"
            },
            "duration_minutes": 50,
            "booking_mode": "class",
            "capacity": 6,
            "prices": {
              "ILS": 12000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "שיעור פרטי על רפורמר",
              "en": "Private reformer session"
            },
            "duration_minutes": 55,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 28000
            },
            "color": "#f59e0b"
          }
        ]
      },
      {
        "key": "yoga",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "יוגה ויניאסה",
              "en": "Vinyasa yoga"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 15,
            "prices": {
              "ILS": 6000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "יוגה למתחילים",
              "en": "Beginners' yoga"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 15,
            "prices": {
              "ILS": 6000
            },
            "color": "#22c55e"
          },
          {
            "names": {
              "he": "שיעור יוגה פרטי",
              "en": "Private yoga"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 25000
            },
            "color": "#6366f1"
          }
        ]
      },
      {
        "key": "crossfit",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "אימון היום (WOD)",
              "en": "WOD"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 16,
            "prices": {
              "ILS": 7000
            },
            "color": "#ef4444"
          },
          {
            "names": {
              "he": "שיעור יסודות למתחילים",
              "en": "Foundations"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 6,
            "prices": {
              "ILS": 8000
            },
            "color": "#f59e0b"
          }
        ]
      },
      {
        "key": "functional",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "אימון פונקציונלי",
              "en": "Functional training"
            },
            "duration_minutes": 50,
            "booking_mode": "class",
            "capacity": 12,
            "prices": {
              "ILS": 6000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "קבוצה קטנה",
              "en": "Small group"
            },
            "duration_minutes": 45,
            "booking_mode": "class",
            "capacity": 5,
            "prices": {
              "ILS": 10000
            },
            "color": "#8b5cf6"
          }
        ]
      },
      {
        "key": "personal_trainer",
        "status": "live",
        "booking_requires_plan": false,
        "default_services": [
          {
            "names": {
              "he": "אימון אישי",
              "en": "Personal training"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 25000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "אימון זוגי",
              "en": "Partner training"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 35000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "הערכת כושר",
              "en": "Fitness assessment"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 15000
            },
            "color": "#10b981"
          }
        ],
        "default_plans": [
          {
            "names": {
              "he": "חבילת 10 אימונים אישיים",
              "en": "10 personal sessions"
            },
            "kind": "punch_card",
            "validity_days": 120,
            "credits": 10,
            "prices": {
              "ILS": 220000
            }
          }
        ]
      }
    ]
  },
  {
    "key": "beauty",
    "order": 2,
    "status": "live",
    "icon": "scissors",
    "color": "from-pink-500 to-rose-500",
    "terms": "beauty",
    "client_term": "client",
    "booking_modes": [
      "appointment"
    ],
    "cancellation_window_minutes": 180,
    "booking_requires_plan": false,
    "default_preset": "growing",
    "recommended_modules": [
      "client_app",
      "whatsapp"
    ],
    "client_fields": [
      {
        "key": "hair_type",
        "kind": "select",
        "options": [
          "straight",
          "wavy",
          "curly",
          "coily"
        ]
      },
      {
        "key": "color_formula",
        "kind": "long_text",
        "max_length": 1000
      },
      {
        "key": "allergies",
        "kind": "text"
      }
    ],
    "default_services": [
      {
        "names": {
          "he": "תספורת גברים",
          "en": "Men's haircut"
        },
        "duration_minutes": 30,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 8000
        },
        "color": "#6366f1"
      },
      {
        "names": {
          "he": "תספורת ועיצוב נשים",
          "en": "Women's cut & style"
        },
        "duration_minutes": 60,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 18000
        },
        "color": "#ec4899"
      },
      {
        "names": {
          "he": "צבע שורשים",
          "en": "Root color"
        },
        "duration_minutes": 90,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 25000
        },
        "color": "#f59e0b"
      },
      {
        "names": {
          "he": "עיצוב זקן",
          "en": "Beard trim"
        },
        "duration_minutes": 20,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 5000
        },
        "color": "#10b981"
      }
    ],
    "children": [
      {
        "key": "hair_salon",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "תספורת ועיצוב נשים",
              "en": "Women's cut & style"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 18000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "פן",
              "en": "Blow-dry"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 12000
            },
            "color": "#8b5cf6"
          },
          {
            "names": {
              "he": "צבע שורשים",
              "en": "Root color"
            },
            "duration_minutes": 90,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 25000
            },
            "color": "#f59e0b"
          },
          {
            "names": {
              "he": "גוונים",
              "en": "Highlights"
            },
            "duration_minutes": 150,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 60000
            },
            "color": "#ef4444"
          }
        ]
      },
      {
        "key": "barbershop",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "תספורת גברים",
              "en": "Men's haircut"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 8000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "עיצוב זקן",
              "en": "Beard trim"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 5000
            },
            "color": "#10b981"
          },
          {
            "names": {
              "he": "תספורת וזקן",
              "en": "Haircut & beard"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 11000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "תספורת ילדים",
              "en": "Kids' haircut"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 6000
            },
            "color": "#f59e0b"
          }
        ]
      },
      {
        "key": "cosmetics",
        "status": "live",
        "client_fields": [
          {
            "key": "skin_type",
            "kind": "select",
            "options": [
              "normal",
              "dry",
              "oily",
              "combination",
              "sensitive"
            ]
          },
          {
            "key": "allergies",
            "kind": "text"
          },
          {
            "key": "treatment_notes",
            "kind": "long_text",
            "max_length": 1000
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "טיפול פנים קלאסי",
              "en": "Classic facial"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 30000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "ניקוי עמוק",
              "en": "Deep cleansing"
            },
            "duration_minutes": 75,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 35000
            },
            "color": "#8b5cf6"
          },
          {
            "names": {
              "he": "עיצוב גבות",
              "en": "Eyebrow shaping"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 6000
            },
            "color": "#f59e0b"
          },
          {
            "names": {
              "he": "שעווה",
              "en": "Waxing"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 8000
            },
            "color": "#10b981"
          }
        ]
      },
      {
        "key": "nails",
        "status": "live",
        "client_fields": [
          {
            "key": "allergies",
            "kind": "text"
          },
          {
            "key": "preferences",
            "kind": "long_text",
            "max_length": 1000
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "מניקור ג'ל",
              "en": "Gel manicure"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 15000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "פדיקור",
              "en": "Pedicure"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 17000
            },
            "color": "#8b5cf6"
          },
          {
            "names": {
              "he": "בניית ציפורניים",
              "en": "Nail extensions"
            },
            "duration_minutes": 90,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 25000
            },
            "color": "#f59e0b"
          },
          {
            "names": {
              "he": "הסרת ג'ל",
              "en": "Gel removal"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 5000
            },
            "color": "#10b981"
          }
        ]
      },
      {
        "key": "laser",
        "status": "live",
        "client_fields": [
          {
            "key": "skin_type",
            "kind": "select",
            "options": [
              "normal",
              "dry",
              "oily",
              "combination",
              "sensitive"
            ]
          },
          {
            "key": "medications",
            "kind": "text"
          },
          {
            "key": "allergies",
            "kind": "text"
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "לייזר — אזור קטן",
              "en": "Laser — small area"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 20000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "לייזר — אזור גדול",
              "en": "Laser — large area"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 45000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "לייזר — גוף מלא",
              "en": "Laser — full body"
            },
            "duration_minutes": 90,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 90000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "פגישת ייעוץ ובדיקת רגישות",
              "en": "Consultation & patch test"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 10000
            },
            "color": "#10b981"
          }
        ],
        "default_plans": [
          {
            "names": {
              "he": "סדרת 6 טיפולים",
              "en": "Series of 6 treatments"
            },
            "kind": "punch_card",
            "validity_days": 365,
            "credits": 6,
            "prices": {
              "ILS": 200000
            }
          }
        ]
      },
      {
        "key": "spa",
        "status": "live",
        "client_fields": [
          {
            "key": "pressure",
            "kind": "select",
            "options": [
              "light",
              "medium",
              "strong"
            ]
          },
          {
            "key": "allergies",
            "kind": "text"
          },
          {
            "key": "health_notes",
            "kind": "long_text",
            "max_length": 1000
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "עיסוי שוודי",
              "en": "Swedish massage"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 35000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "עיסוי רקמות עמוק",
              "en": "Deep tissue massage"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 40000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "עיסוי זוגי",
              "en": "Couples massage"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 70000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "טיפול גוף",
              "en": "Body treatment"
            },
            "duration_minutes": 75,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 45000
            },
            "color": "#f59e0b"
          }
        ]
      }
    ]
  },
  {
    "key": "clinic",
    "order": 3,
    "status": "live",
    "icon": "stethoscope",
    "color": "from-teal-500 to-emerald-500",
    "terms": "clinic",
    "client_term": "patient",
    "booking_modes": [
      "appointment"
    ],
    "cancellation_window_minutes": 1440,
    "booking_requires_plan": false,
    "default_preset": "growing",
    "recommended_modules": [
      "whatsapp"
    ],
    "client_fields": [
      {
        "key": "id_number",
        "kind": "text",
        "max_length": 20
      },
      {
        "key": "health_fund",
        "kind": "select",
        "options": [
          "clalit",
          "maccabi",
          "meuhedet",
          "leumit",
          "private"
        ]
      },
      {
        "key": "referred_by",
        "kind": "text"
      },
      {
        "key": "allergies",
        "kind": "text"
      }
    ],
    "default_services": [
      {
        "names": {
          "he": "פגישת היכרות",
          "en": "First visit"
        },
        "duration_minutes": 60,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 35000
        },
        "color": "#14b8a6"
      },
      {
        "names": {
          "he": "טיפול",
          "en": "Treatment"
        },
        "duration_minutes": 45,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 30000
        },
        "color": "#6366f1"
      },
      {
        "names": {
          "he": "פגישת מעקב",
          "en": "Follow-up"
        },
        "duration_minutes": 30,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 20000
        },
        "color": "#8b5cf6"
      }
    ],
    "children": [
      {
        "key": "physiotherapy",
        "status": "live",
        "extra_client_fields": [
          {
            "key": "injury",
            "kind": "long_text",
            "max_length": 1000
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "אבחון ראשוני",
              "en": "Initial assessment"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 35000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "טיפול פיזיותרפיה",
              "en": "Physiotherapy session"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 28000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "שיקום ספורט",
              "en": "Sports rehabilitation"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 32000
            },
            "color": "#f59e0b"
          }
        ],
        "default_plans": [
          {
            "names": {
              "he": "סדרת 10 טיפולים",
              "en": "Series of 10 sessions"
            },
            "kind": "punch_card",
            "validity_days": 180,
            "credits": 10,
            "prices": {
              "ILS": 250000
            }
          }
        ]
      },
      {
        "key": "dental",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "בדיקה תקופתית",
              "en": "Check-up"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 20000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "ניקוי אבנית (שיננית)",
              "en": "Hygienist cleaning"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 30000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "סתימה",
              "en": "Filling"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 50000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "הלבנת שיניים",
              "en": "Teeth whitening"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 120000
            },
            "color": "#f59e0b"
          }
        ]
      },
      {
        "key": "nutrition",
        "status": "live",
        "extra_client_fields": [
          {
            "key": "dietary_restrictions",
            "kind": "text"
          },
          {
            "key": "goal",
            "kind": "select",
            "options": [
              "weight_loss",
              "strength",
              "flexibility",
              "rehab",
              "general"
            ]
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "פגישת ייעוץ ראשונה",
              "en": "First consultation"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 40000
            },
            "color": "#22c55e"
          },
          {
            "names": {
              "he": "פגישת מעקב",
              "en": "Follow-up"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 20000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "מדידת הרכב גוף",
              "en": "Body composition scan"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 10000
            },
            "color": "#f59e0b"
          }
        ],
        "default_plans": [
          {
            "names": {
              "he": "ליווי — 4 פגישות מעקב",
              "en": "Coaching — 4 follow-ups"
            },
            "kind": "punch_card",
            "validity_days": 90,
            "credits": 4,
            "prices": {
              "ILS": 70000
            }
          }
        ]
      },
      {
        "key": "aesthetics",
        "status": "live",
        "extra_client_fields": [
          {
            "key": "medications",
            "kind": "text"
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "פגישת ייעוץ",
              "en": "Consultation"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 20000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "בוטוקס",
              "en": "Botox"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 120000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "חומרי מילוי",
              "en": "Fillers"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 180000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "טיפול עור",
              "en": "Skin treatment"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 60000
            },
            "color": "#f59e0b"
          }
        ]
      },
      {
        "key": "therapy",
        "status": "live",
        "client_fields": [
          {
            "key": "referred_by",
            "kind": "text"
          },
          {
            "key": "emergency_contact",
            "kind": "text"
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "פגישת היכרות",
              "en": "Intake session"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 45000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "פגישה",
              "en": "Session"
            },
            "duration_minutes": 50,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 40000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "פגישה זוגית",
              "en": "Couples session"
            },
            "duration_minutes": 75,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 55000
            },
            "color": "#8b5cf6"
          }
        ]
      }
    ]
  },
  {
    "key": "classes",
    "order": 4,
    "status": "live",
    "icon": "graduation-cap",
    "color": "from-sky-500 to-blue-600",
    "terms": "classes",
    "client_term": "student",
    "booking_modes": [
      "class",
      "appointment"
    ],
    "cancellation_window_minutes": 720,
    "booking_requires_plan": true,
    "default_preset": "growing",
    "recommended_modules": [
      "client_app",
      "whatsapp"
    ],
    "client_fields": [
      {
        "key": "level",
        "kind": "select",
        "options": [
          "beginner",
          "intermediate",
          "advanced"
        ]
      },
      {
        "key": "birth_date",
        "kind": "date"
      },
      {
        "key": "parent_name",
        "kind": "text"
      },
      {
        "key": "parent_phone",
        "kind": "text",
        "max_length": 30
      }
    ],
    "default_plans": [
      {
        "names": {
          "he": "מנוי חודשי",
          "en": "Monthly membership"
        },
        "kind": "membership",
        "validity_days": 30,
        "prices": {
          "ILS": 35000
        }
      },
      {
        "names": {
          "he": "מנוי לתקופה (3 חודשים)",
          "en": "Term (3 months)"
        },
        "kind": "membership",
        "validity_days": 90,
        "prices": {
          "ILS": 95000
        }
      },
      {
        "names": {
          "he": "שיעור ניסיון",
          "en": "Trial lesson"
        },
        "kind": "punch_card",
        "validity_days": 14,
        "credits": 1,
        "prices": {
          "ILS": 5000
        }
      }
    ],
    "children": [
      {
        "key": "dance",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "בלט ילדים",
              "en": "Kids' ballet"
            },
            "duration_minutes": 45,
            "booking_mode": "class",
            "capacity": 15,
            "prices": {
              "ILS": 6000
            },
            "color": "#ec4899"
          },
          {
            "names": {
              "he": "היפ־הופ",
              "en": "Hip-hop"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 20,
            "prices": {
              "ILS": 6000
            },
            "color": "#8b5cf6"
          },
          {
            "names": {
              "he": "מחול עכשווי",
              "en": "Contemporary"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 15,
            "prices": {
              "ILS": 6000
            },
            "color": "#0ea5e9"
          }
        ]
      },
      {
        "key": "martial_arts",
        "status": "live",
        "extra_client_fields": [
          {
            "key": "belt",
            "kind": "text",
            "max_length": 40
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "קראטה ילדים",
              "en": "Kids' karate"
            },
            "duration_minutes": 45,
            "booking_mode": "class",
            "capacity": 20,
            "prices": {
              "ILS": 5000
            },
            "color": "#ef4444"
          },
          {
            "names": {
              "he": "קרב מגע",
              "en": "Krav Maga"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 20,
            "prices": {
              "ILS": 6000
            },
            "color": "#f59e0b"
          },
          {
            "names": {
              "he": "ג'יו־ג'יטסו ברזילאי",
              "en": "Brazilian jiu-jitsu"
            },
            "duration_minutes": 60,
            "booking_mode": "class",
            "capacity": 16,
            "prices": {
              "ILS": 7000
            },
            "color": "#6366f1"
          }
        ]
      },
      {
        "key": "music",
        "status": "live",
        "extra_client_fields": [
          {
            "key": "instrument",
            "kind": "text",
            "max_length": 60
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "שיעור גיטרה",
              "en": "Guitar lesson"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 18000
            },
            "color": "#f59e0b"
          },
          {
            "names": {
              "he": "שיעור פסנתר",
              "en": "Piano lesson"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 18000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "שיעור פיתוח קול",
              "en": "Voice lesson"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 20000
            },
            "color": "#ec4899"
          }
        ],
        "default_plans": [
          {
            "names": {
              "he": "4 שיעורים בחודש",
              "en": "4 lessons a month"
            },
            "kind": "punch_card",
            "validity_days": 35,
            "credits": 4,
            "prices": {
              "ILS": 65000
            }
          },
          {
            "names": {
              "he": "שיעור ניסיון",
              "en": "Trial lesson"
            },
            "kind": "punch_card",
            "validity_days": 14,
            "credits": 1,
            "prices": {
              "ILS": 10000
            }
          }
        ]
      },
      {
        "key": "tutoring",
        "status": "live",
        "extra_client_fields": [
          {
            "key": "school_grade",
            "kind": "text",
            "max_length": 40
          },
          {
            "key": "subjects",
            "kind": "text"
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "שיעור פרטי",
              "en": "Private lesson"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 18000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "קבוצה קטנה",
              "en": "Small group"
            },
            "duration_minutes": 90,
            "booking_mode": "class",
            "capacity": 6,
            "prices": {
              "ILS": 12000
            },
            "color": "#8b5cf6"
          },
          {
            "names": {
              "he": "הכנה לבגרות",
              "en": "Exam preparation"
            },
            "duration_minutes": 90,
            "booking_mode": "class",
            "capacity": 15,
            "prices": {
              "ILS": 10000
            },
            "color": "#f59e0b"
          }
        ],
        "default_plans": [
          {
            "names": {
              "he": "חבילת 10 שיעורים",
              "en": "10 lessons"
            },
            "kind": "punch_card",
            "validity_days": 120,
            "credits": 10,
            "prices": {
              "ILS": 160000
            }
          }
        ]
      },
      {
        "key": "kids_activities",
        "status": "live",
        "default_services": [
          {
            "names": {
              "he": "חוג העשרה",
              "en": "Enrichment class"
            },
            "duration_minutes": 45,
            "booking_mode": "class",
            "capacity": 12,
            "prices": {
              "ILS": 5000
            },
            "color": "#22c55e"
          },
          {
            "names": {
              "he": "חוג פעוטות (עם הורה)",
              "en": "Toddlers with a parent"
            },
            "duration_minutes": 45,
            "booking_mode": "class",
            "capacity": 10,
            "prices": {
              "ILS": 5500
            },
            "color": "#f59e0b"
          }
        ]
      }
    ]
  },
  {
    "key": "automotive",
    "order": 5,
    "status": "live",
    "icon": "car",
    "color": "from-amber-500 to-orange-500",
    "terms": "automotive",
    "client_term": "customer",
    "booking_modes": [
      "appointment"
    ],
    "cancellation_window_minutes": 1440,
    "booking_requires_plan": false,
    "default_preset": "starter",
    "recommended_modules": [
      "whatsapp"
    ],
    "client_fields": [
      {
        "key": "plate",
        "kind": "text",
        "max_length": 12
      },
      {
        "key": "make",
        "kind": "text",
        "max_length": 40
      },
      {
        "key": "model",
        "kind": "text",
        "max_length": 40
      },
      {
        "key": "year",
        "kind": "number"
      },
      {
        "key": "mileage",
        "kind": "number"
      },
      {
        "key": "next_inspection",
        "kind": "date"
      }
    ],
    "default_services": [
      {
        "names": {
          "he": "טיפול תקופתי",
          "en": "Periodic service"
        },
        "duration_minutes": 120,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 60000
        },
        "color": "#f59e0b"
      },
      {
        "names": {
          "he": "החלפת שמן ומסננים",
          "en": "Oil & filter change"
        },
        "duration_minutes": 45,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 25000
        },
        "color": "#0ea5e9"
      },
      {
        "names": {
          "he": "בדיקה לפני טסט",
          "en": "Pre-inspection check"
        },
        "duration_minutes": 60,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 20000
        },
        "color": "#10b981"
      },
      {
        "names": {
          "he": "אבחון תקלה",
          "en": "Diagnostics"
        },
        "duration_minutes": 60,
        "booking_mode": "appointment",
        "prices": {
          "ILS": 30000
        },
        "color": "#ef4444"
      }
    ],
    "children": [
      {
        "key": "garage",
        "status": "live"
      },
      {
        "key": "detailing",
        "status": "live",
        "client_fields": [
          {
            "key": "plate",
            "kind": "text",
            "max_length": 12
          },
          {
            "key": "make",
            "kind": "text",
            "max_length": 40
          },
          {
            "key": "model",
            "kind": "text",
            "max_length": 40
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "שטיפה חיצונית",
              "en": "Exterior wash"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 6000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "שטיפה פנים וחוץ",
              "en": "Full wash, inside and out"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 12000
            },
            "color": "#14b8a6"
          },
          {
            "names": {
              "he": "דיטיילינג מלא",
              "en": "Full detailing"
            },
            "duration_minutes": 180,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 60000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "ציפוי קרמי",
              "en": "Ceramic coating"
            },
            "duration_minutes": 480,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 250000
            },
            "color": "#f59e0b"
          }
        ]
      },
      {
        "key": "tires",
        "status": "live",
        "client_fields": [
          {
            "key": "plate",
            "kind": "text",
            "max_length": 12
          },
          {
            "key": "make",
            "kind": "text",
            "max_length": 40
          },
          {
            "key": "model",
            "kind": "text",
            "max_length": 40
          },
          {
            "key": "tire_size",
            "kind": "text",
            "max_length": 20
          }
        ],
        "default_services": [
          {
            "names": {
              "he": "תיקון תקר",
              "en": "Puncture repair"
            },
            "duration_minutes": 20,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 6000
            },
            "color": "#ef4444"
          },
          {
            "names": {
              "he": "החלפת צמיגים",
              "en": "Tire replacement"
            },
            "duration_minutes": 60,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 20000
            },
            "color": "#6366f1"
          },
          {
            "names": {
              "he": "כיוון פרונט",
              "en": "Wheel alignment"
            },
            "duration_minutes": 45,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 18000
            },
            "color": "#0ea5e9"
          },
          {
            "names": {
              "he": "איזון גלגלים",
              "en": "Wheel balancing"
            },
            "duration_minutes": 30,
            "booking_mode": "appointment",
            "prices": {
              "ILS": 10000
            },
            "color": "#10b981"
          }
        ]
      }
    ]
  },
  {
    "key": "sports",
    "order": 6,
    "status": "planned",
    "icon": "trophy",
    "color": "from-lime-500 to-green-600"
  },
  {
    "key": "home_services",
    "order": 7,
    "status": "planned",
    "icon": "wrench",
    "color": "from-slate-500 to-zinc-700"
  },
  {
    "key": "pets",
    "order": 8,
    "status": "planned",
    "icon": "paw-print",
    "color": "from-orange-400 to-amber-600"
  },
  {
    "key": "events",
    "order": 9,
    "status": "planned",
    "icon": "camera",
    "color": "from-fuchsia-500 to-purple-600"
  },
  {
    "key": "professional",
    "order": 10,
    "status": "planned",
    "icon": "briefcase",
    "color": "from-cyan-600 to-sky-700"
  }
];
