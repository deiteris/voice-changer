import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "../../../001_provider/001_AppStateProvider";
import { useMessageBuilder } from "../../../hooks/useMessageBuilder";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    LineController,
    Filler,
  } from 'chart.js';
import { Chart } from 'react-chartjs-2';
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faWaveSquare } from "@fortawesome/free-solid-svg-icons";

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    LineController,
    Filler,
);

export type PortraitProps = {};

const performanceState = (time: number, chunkTime: number) => {
    if (time > chunkTime) return "over";
    if (time * 1.2 > chunkTime) return "near";
    return "within";
};

export const Portrait = (_props: PortraitProps) => {
    const { serverSetting, performance } = useAppState();
    const messageBuilderState = useMessageBuilder();

    const [perfTooltip, setPerfTooltip] = useState(0);
    const elPerfChartRef = useRef<ChartJS | null>(null);
    const elVolRef = useRef<HTMLElement | null>(null);
    const elChunkTimeRef = useRef<HTMLElement | null>(null);
    const elPingRef = useRef<HTMLElement | null>(null);
    const elTotalRef = useRef<HTMLElement | null>(null);
    const elPerfRef = useRef<HTMLElement | null>(null);
    const MAX_DATA_POINTS = 50;

    const [lastReport, setLastReport] = useState(Date.now())

    useMemo(() => {
        messageBuilderState.setMessage(__filename, "terms_of_use", { ja: "利用規約", en: "terms of use" });
    }, []);

    const selected = useMemo(() => {
        if (serverSetting.serverSetting.modelSlotIndex == undefined) {
            return;
        } else {
            return serverSetting.serverSetting.modelSlots[serverSetting.serverSetting.modelSlotIndex];
        }
    }, [serverSetting.serverSetting.modelSlotIndex, serverSetting.serverSetting.modelSlots]);

    useEffect(() => {
        if (!elVolRef.current || !elPerfChartRef.current || !elChunkTimeRef.current || !elPingRef.current || !elTotalRef.current || !elPerfRef.current) {
            return;
        }

        const now = Date.now()
        if (now - lastReport <= 100) {
            return
        }
        setLastReport(now)

        const volumeDb = Math.max(Math.round(20 * Math.log10(performance.vol)), -90);
        const chunkTime = ((serverSetting.serverSetting.serverReadChunkSize * 128 * 1000) / 48000);
        const totalLatencyTime = Math.ceil(chunkTime + performance.responseTime + serverSetting.serverSetting.crossFadeOverlapSize * 1000);

        elPerfRef.current.dataset.timing = performanceState(performance.mainprocessTime, chunkTime);

        elVolRef.current.innerHTML = volumeDb.toString();
        elChunkTimeRef.current.innerHTML = chunkTime.toFixed(1);
        elPingRef.current.innerHTML = performance.responseTime.toString();
        elTotalRef.current.innerHTML = totalLatencyTime.toString();
        elPerfRef.current.innerHTML = performance.mainprocessTime.toString();

        if (performance.mainprocessTime > 0) {
            if (elPerfChartRef.current.data.labels!.length > MAX_DATA_POINTS) {
                elPerfChartRef.current.data.labels!.shift()
                elPerfChartRef.current.data.datasets[0].data.shift();
            }
            elPerfChartRef.current.data.labels!.push(Date.now())
            elPerfChartRef.current.data.datasets[0].data.push(performance.mainprocessTime)
            elPerfChartRef.current.update('none')
        }
    }, [performance, serverSetting.serverSetting.crossFadeOverlapSize, serverSetting.serverSetting.serverReadChunkSize])

    useEffect(() => {
        if (!elPerfRef.current) {
            return
        }

        const chunkTime = ((serverSetting.serverSetting.serverReadChunkSize * 128 * 1000) / 48000);

        elPerfRef.current.dataset.timing = performanceState(perfTooltip, chunkTime);

        elPerfRef.current.innerHTML = perfTooltip.toString();
    }, [perfTooltip])

    const portrait = useMemo(() => {
        if (!selected) {
            return (
                <div className="studio-portrait-empty">
                    <FontAwesomeIcon icon={faWaveSquare} />
                    <p>Select a voice model</p>
                </div>
            );
        }

        const modelDir = serverSetting.serverSetting.voiceChangerParams.model_dir;
        const icon = selected.iconFile.length > 0 ? modelDir + "/" + selected.slotIndex + "/" + selected.iconFile.split(/[\/\\]/).pop() : "./assets/icons/human.png";
        const portrait = <img className="portrait" src={icon} alt={selected.name} />;
        const selectedTermOfUseUrlLink = selected.termsOfUseUrl ? (
            <a href={selected.termsOfUseUrl} target="_blank" rel="noopener noreferrer" className="studio-model-terms">
                {messageBuilderState.getMessage(__filename, "terms_of_use")}
            </a>
        ) : (
            <></>
        );

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'nearest' as const,
                axis: 'x' as const,
                intersect: false,
            },
            plugins: {
                tooltip: {
                    enabled: false,
                    external: (context: any) => {
                        if (context.tooltip.dataPoints) {
                            setPerfTooltip(context.tooltip.dataPoints[0].parsed.y)
                        }
                    }
                },
                title: {
                    display: false,
                },
            },
            scales: {
                x: {
                    ticks: {
                        display: false,
                    },
                    min: 0,
                    grid: {
                        display: false
                    },
                },
                y: {
                    ticks: {
                        display: false,
                    },
                    min: 0,
                    grid: {
                        display: false
                    },
                }
            },
        };

        const data = {
            labels: [],
            datasets: [
                {
                    data: [],
                    fill: true,
                    borderColor: '#8264c8',
                    backgroundColor: 'rgba(130, 100, 200, 0.16)',
                    pointRadius: 0,
                    borderWidth: 2,
                }
            ]
        }

        return (
            <div className="studio-portrait">
                <div className="studio-portrait-art">
                    {portrait}
                </div>
                <div className="studio-portrait-meta">
                    <span>{serverSetting.serverSetting.useONNX ? selected.modelTypeOnnx : selected.modelType}</span>
                    {selectedTermOfUseUrlLink}
                </div>
                <dl className="studio-signal">
                    <div><dt>Input</dt><dd><span ref={elVolRef}>-90</span> dB</dd></div>
                    <div><dt>Ping</dt><dd><span ref={elPingRef}>0</span> ms</dd></div>
                    <div><dt>Latency</dt><dd><span ref={elTotalRef}>0</span> ms</dd></div>
                    <div><dt>Processing</dt><dd><span ref={elPerfRef}>0</span> / <span ref={elChunkTimeRef}>0</span> ms</dd></div>
                </dl>
                <div className="studio-performance-chart">
                    <Chart ref={elPerfChartRef} type="line" options={options} data={data} role="img" aria-label="Processing time history" />
                </div>
            </div>
        );
    }, [selected, serverSetting.serverSetting.useONNX]);

    return portrait;
};
