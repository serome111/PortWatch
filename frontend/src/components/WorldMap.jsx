import React, { useMemo } from "react"
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps"
import { scaleLinear } from "d3-scale"
import { Tooltip } from "react-tooltip"
import * as topojson from "topojson-client"
import { useTranslation } from 'react-i18next'

// Usamos el archivo local descargado (world-atlas 110m)
const geoUrl = "/world-countries.json"

// Mapeo manual ISO-2 a ISO Numeric (Standard)
// Solo los principales para demo, idealmente usar librería 'i18n-iso-countries'
const iso2ToId = {
    "US": "840", "CA": "124", "MX": "484", "BR": "076", "AR": "032",
    "CO": "170", "PE": "604", "CL": "152", "ES": "724", "FR": "250",
    "DE": "276", "IT": "380", "GB": "826", "RU": "643", "CN": "156",
    "JP": "392", "IN": "356", "AU": "036", "ZA": "710", "EG": "818",
    "NL": "528", "BE": "056", "CH": "756", "SE": "752", "NO": "578",
    "DK": "208", "FI": "246", "IE": "372", "PT": "620", "GR": "300",
    "TR": "792", "KR": "410", "SG": "702", "HK": "344", "TW": "158",
    "UA": "804", "PL": "616", "RO": "642", "CZ": "203", "HU": "348",
    "AT": "040", "NZ": "554", "ID": "360", "MY": "458", "TH": "764",
    "VN": "704", "PH": "608", "IL": "376", "SA": "682", "AE": "784"
}

export function WorldMap({ rows, onCountrySelect, selectedCountry }) {
    const { t } = useTranslation()
    // Agrupar por país (ISO 2 letras)
    const countries = useMemo(() => {
        const counts = {}
        rows.forEach(r => {
            if (r.country) {
                // Convertir ISO-2 a Numeric ID si es posible
                const id = iso2ToId[r.country]
                if (id) {
                    counts[id] = (counts[id] || 0) + 1
                }
                // Fallback: guardar también por ISO por si acaso el mapa soporta ISO
                counts[r.country] = (counts[r.country] || 0) + 1
            }
        })
        return counts
    }, [rows])

    const maxCount = Math.max(...Object.values(countries), 0)
    const colorScale = scaleLinear()
        .domain([0, maxCount || 1])
        .range(["#334155", "#10b981"]) // Slate-700 to Emerald-500

    return (
        <div className="w-full h-[300px] bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden relative">
            <div className="absolute top-4 left-4 z-10 pointer-events-none">
                <h3 className="text-sm font-medium text-slate-300">{t('map.title')}</h3>
                <p className="text-xs text-slate-500">
                    {Object.keys(countries).length} {t('map.countries_connected')}
                </p>
            </div>

            <ComposableMap
                projectionConfig={{ scale: 140, center: [0, 20] }}
                width={800}
                height={400}
                style={{ width: "100%", height: "100%" }}
            >
                <Geographies geography={geoUrl}>
                    {({ geographies }) =>
                        geographies.map((geo) => {
                            // world-atlas usa IDs numéricos (strings)
                            const id = geo.id
                            const count = countries[id] || 0
                            const name = geo.properties.name // world-atlas usually has name in properties

                            // Find ISO code for this ID to pass back to parent
                            const isoCode = Object.keys(iso2ToId).find(key => iso2ToId[key] === id)
                            const isSelected = selectedCountry && isoCode === selectedCountry

                            return (
                                <Geography
                                    key={geo.rsmKey}
                                    geography={geo}
                                    fill={
                                        isSelected ? "#3b82f6" : // Blue-500 if selected
                                            count > 0 ? colorScale(count) : "#1e293b" // Slate-800 default
                                    }
                                    stroke={isSelected ? "#60a5fa" : "#0f172a"} // Blue-400 if selected
                                    strokeWidth={isSelected ? 1 : 0.5}
                                    data-tooltip-id="map-tooltip"
                                    data-tooltip-content={name ? `${name}: ${count} conexiones` : ""}
                                    onClick={() => {
                                        if (count > 0 && isoCode) {
                                            onCountrySelect(isSelected ? null : isoCode)
                                        }
                                    }}
                                    style={{
                                        default: { outline: "none", cursor: count > 0 ? "pointer" : "default" },
                                        hover: {
                                            fill: count > 0 ? "#34d399" : "#334155",
                                            outline: "none",
                                            cursor: count > 0 ? "pointer" : "default"
                                        },
                                        pressed: { outline: "none" },
                                    }}
                                />
                            )
                        })
                    }
                </Geographies>
            </ComposableMap>
            <Tooltip id="map-tooltip" style={{ backgroundColor: "#0f172a", color: "#fff" }} />
        </div>
    )
}
