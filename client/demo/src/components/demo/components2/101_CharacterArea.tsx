import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "../../../001_provider/001_AppStateProvider";
import { useGuiState } from "../001_GuiStateProvider";
import { useMessageBuilder } from "../../../hooks/useMessageBuilder";
import { TuningArea } from "./101-1_TuningArea";
import { IndexArea } from "./101-2_IndexArea";
import { SpeakerArea } from "./101-3_SpeakerArea";
import { FormantShiftArea } from "./101-4_FormantShiftArea";
import { Portrait } from "./101-0_Portrait";
import { toast } from "react-toastify";

export type CharacterAreaProps = {};

export const CharacterArea = (_props: CharacterAreaProps) => {
    const { serverSetting, initializedRef, setting, setVoiceChangerClientSetting, start, stop } = useAppState();
    const guiState = useGuiState();
    const messageBuilderState = useMessageBuilder();
    useMemo(() => {
        messageBuilderState.setMessage(__filename, "save_default", { ja: "設定保存", en: "save setting" });
    }, []);

    const selected = useMemo(() => {
        if (serverSetting.serverSetting.modelSlotIndex == undefined) {
            return;
        } else {
            return serverSetting.serverSetting.modelSlots[serverSetting.serverSetting.modelSlotIndex];
        }
    }, [serverSetting.serverSetting.modelSlotIndex, serverSetting.serverSetting.modelSlots]);

    const [startWithAudioContextCreate, setStartWithAudioContextCreate] = useState<boolean>(false);
    useEffect(() => {
        if (!startWithAudioContextCreate) {
            return;
        }
        guiState.setIsConverting(true);
        start();
    }, [startWithAudioContextCreate]);

    const nameArea = useMemo(() => {
        if (!selected) {
            return <></>;
        }
        return (
            <div className="character-area-control">
                <div className="character-area-control-title">Name:</div>
                <div className="character-area-control-field">
                    <div className="character-area-text">
                        {selected.name}
                    </div>
                </div>
            </div>
        );
    }, [selected]);

    const serverAudioRequestPending = useRef(false);
    useEffect(() => {
        if (serverSetting.serverSetting.enableServerAudio) {
            guiState.setIsConverting(Boolean(serverSetting.serverSetting.serverAudioStated));
        }
    }, [serverSetting.serverSetting.enableServerAudio, serverSetting.serverSetting.serverAudioStated]);

    const startControl = useMemo(() => {
        const setServerAudioRunning = async (running: boolean) => {
            if (serverAudioRequestPending.current) return;
            serverAudioRequestPending.current = true;
            try {
                await serverSetting.updateServerSettings({ ...serverSetting.serverSetting, serverAudioStated: Number(running) });
            } catch (error) {
                toast.error(error instanceof Error ? error.message : String(error));
            } finally {
                serverAudioRequestPending.current = false;
            }
        };
        const onStartClicked = async () => {
            if (serverSetting.serverSetting.modelSlotIndex === -1) {
                toast.warn('Select a voice model first.')
                return
            }
            if (serverSetting.serverSetting.enableServerAudio == 0) {
                if (!setting.voiceChangerClientSetting.audioInput || setting.voiceChangerClientSetting.audioInput == 'none') {
                    toast.warn('Select an audio input device.')
                    return
                }
                // TODO: Refactor
                if (guiState.audioOutputForGUI == 'none') {
                    toast.warn('Select an audio output device.')
                    return
                }

                if (!initializedRef.current) {
                    while (true) {
                        await new Promise<void>((resolve) => {
                            setTimeout(resolve, 500);
                        });
                        if (initializedRef.current) {
                            break;
                        }
                    }
                    setStartWithAudioContextCreate(true);
                } else {
                    guiState.setIsConverting(true);
                    await start();
                }
            } else {
                if (serverSetting.serverSetting.serverInputDeviceId == -1) {
                    toast.warn('Select an audio input device.')
                    return
                }
                if (serverSetting.serverSetting.serverOutputDeviceId == -1) {
                    toast.warn('Select an audio output device.')
                    return
                }
                await setServerAudioRunning(true);
            }
        };
        const onStopClicked = async () => {
            if (serverSetting.serverSetting.enableServerAudio == 0) {
                guiState.setIsConverting(false);
                await stop();
            } else {
                await setServerAudioRunning(false);
            }
        };
        const onPassThroughClicked = async () => {
            if (serverSetting.serverSetting.passThrough == false) {
                if (setting.voiceChangerClientSetting.passThroughConfirmationSkip) {
                    serverSetting.updateServerSettings({ ...serverSetting.serverSetting, passThrough: true });
                    guiState.stateControls.showEnablePassThroughDialogCheckbox.updateState(false);
                } else {
                    guiState.stateControls.showEnablePassThroughDialogCheckbox.updateState(true);
                }
            } else {
                serverSetting.updateServerSettings({ ...serverSetting.serverSetting, passThrough: false });
            }
        };
        const startClassName = guiState.isConverting ? "character-area-control-button-active" : "character-area-control-button-stanby";
        const stopClassName = guiState.isConverting ? "character-area-control-button-stanby" : "character-area-control-button-active";
        const passThruClassName = serverSetting.serverSetting.passThrough == false ? "character-area-control-passthru-button-stanby" : "character-area-control-passthru-button-active blinking";

        return (
            <div className="character-area-control">
                <div className="character-area-control-buttons">
                    <div onClick={onStartClicked} className={startClassName}>
                        start
                    </div>
                    <div onClick={onStopClicked} className={stopClassName}>
                        stop
                    </div>

                    <div onClick={onPassThroughClicked} className={passThruClassName}>
                        passthru
                    </div>
                </div>
            </div>
        );
    }, [guiState.isConverting, setting.voiceChangerClientSetting.audioInput, guiState.audioOutputForGUI, start, stop, serverSetting.serverSetting, serverSetting.updateServerSettings]);

    const gainControl = useMemo(() => {
        const currentInputGain = serverSetting.serverSetting.enableServerAudio == 0 ? setting.voiceChangerClientSetting.inputGain : serverSetting.serverSetting.serverInputAudioGain;
        const inputValueUpdatedAction =
            serverSetting.serverSetting.enableServerAudio == 0
                ? async (val: number) => {
                      await setVoiceChangerClientSetting({ ...setting.voiceChangerClientSetting, inputGain: val });
                  }
                : async (val: number) => {
                      await serverSetting.updateServerSettings({ ...serverSetting.serverSetting, serverInputAudioGain: val });
                  };

        const currentOutputGain = serverSetting.serverSetting.enableServerAudio == 0 ? setting.voiceChangerClientSetting.outputGain : serverSetting.serverSetting.serverOutputAudioGain;
        const outputValueUpdatedAction =
            serverSetting.serverSetting.enableServerAudio == 0
                ? async (val: number) => {
                      await setVoiceChangerClientSetting({ ...setting.voiceChangerClientSetting, outputGain: val });
                  }
                : async (val: number) => {
                      await serverSetting.updateServerSettings({ ...serverSetting.serverSetting, serverOutputAudioGain: val });
                  };

        const currentMonitorGain = serverSetting.serverSetting.enableServerAudio == 0 ? setting.voiceChangerClientSetting.monitorGain : serverSetting.serverSetting.serverMonitorAudioGain;
        const monitorValueUpdatedAction =
            serverSetting.serverSetting.enableServerAudio == 0
                ? async (val: number) => {
                    await setVoiceChangerClientSetting({ ...setting.voiceChangerClientSetting, monitorGain: val });
                }
                : async (val: number) => {
                    await serverSetting.updateServerSettings({ ...serverSetting.serverSetting, serverMonitorAudioGain: val });
                };

        return (
            <div className="character-area-control">
                <div className="character-area-control-title">VOL:</div>
                <div className="character-area-control-field">
                    <div className="character-area-slider-control">
                        <span className="character-area-slider-control-kind"><a className="hint-text" data-tooltip-id="hint" data-tooltip-content="Input volume.">in</a></span>
                        <span className="character-area-slider-control-slider">
                            <input
                                type="range"
                                min="0.1"
                                max="2.5"
                                step="0.01"
                                value={currentInputGain}
                                onChange={(e) => {
                                    inputValueUpdatedAction(Number(e.target.value));
                                }}
                            ></input>
                        </span>
                        <span className="character-area-slider-control-val">{Math.round(currentInputGain * 100)}%</span>
                    </div>

                    <div className="character-area-slider-control">
                        <span className="character-area-slider-control-kind"><a className="hint-text" data-tooltip-id="hint" data-tooltip-content="Output volume.">out</a></span>
                        <span className="character-area-slider-control-slider">
                            <input
                                type="range"
                                min="0.1"
                                max="4.0"
                                step="0.01"
                                value={currentOutputGain}
                                onChange={(e) => {
                                    outputValueUpdatedAction(Number(e.target.value));
                                }}
                            ></input>
                        </span>
                        <span className="character-area-slider-control-val">{Math.round(currentOutputGain * 100)}%</span>
                    </div>

                    <div className="character-area-slider-control">
                        <span className="character-area-slider-control-kind"><a className="hint-text" data-tooltip-id="hint" data-tooltip-content="Monitor volume.">mon</a></span>
                        <span className="character-area-slider-control-slider">
                            <input
                                type="range"
                                min="0.1"
                                max="4.0"
                                step="0.01"
                                value={currentMonitorGain}
                                onChange={(e) => {
                                    monitorValueUpdatedAction(Number(e.target.value));
                                }}
                            ></input>
                        </span>
                        <span className="character-area-slider-control-val">{Math.round(currentMonitorGain * 100)}%</span>
                    </div>
                </div>
            </div>
        );
    }, [serverSetting.serverSetting, setting, setVoiceChangerClientSetting, serverSetting.updateServerSettings]);

    const modelSlotControl = useMemo(() => {
        if (!selected) {
            return <></>;
        }
        const onUpdateDefaultClicked = async () => {
            await serverSetting.updateModelDefault();
        };

        return (
            <div className="character-area-control" style={{ margin: "0 auto" }}>
                <div className="character-area-control-field">
                    <div className="character-area-buttons">
                        <div className="character-area-button" onClick={onUpdateDefaultClicked}>
                            {messageBuilderState.getMessage(__filename, "save_default")}
                        </div>
                    </div>
                </div>
            </div>
        );
    }, [selected, serverSetting.updateModelDefault]);

    const characterControlArea = useMemo(() => {
        return (
            <div className="character-area-control-area">
                {nameArea}
                {startControl}
                {gainControl}
                <TuningArea />
                <FormantShiftArea />
                <IndexArea />
                <SpeakerArea />
                {modelSlotControl}
            </div>
        )
    }, [startControl, gainControl, modelSlotControl])

    return (
        <div className="character-area">
            <Portrait></Portrait>
            {characterControlArea}
        </div>
    );
};
