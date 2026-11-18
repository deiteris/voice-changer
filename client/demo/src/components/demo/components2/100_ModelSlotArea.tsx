import React, { useState } from "react";
import { faArrowDown19, faArrowDownAZ, faCheck, faSliders, faWaveSquare } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { toast } from "react-toastify";
import { useAppState } from "../../../001_provider/001_AppStateProvider";
import { useGuiState } from "../001_GuiStateProvider";

export type ModelSlotAreaProps = {};

export const ModelSlotArea = (_props: ModelSlotAreaProps) => {
    const { serverSetting } = useAppState();
    const { stateControls } = useGuiState();
    const [sortType, setSortType] = useState<"slot" | "name">("slot");
    const settings = serverSetting.serverSetting;
    const models = (settings.modelSlots ?? []).filter((model) => model.modelFile);
    if (sortType === "name") models.sort((a, b) => a.name.localeCompare(b.name));

    const selectModel = async (slotIndex: typeof settings.modelSlotIndex) => {
        stateControls.showWaitingCheckbox.updateState(true);
        try {
            await serverSetting.updateServerSettings({ ...settings, modelSlotIndex: slotIndex });
        } catch (error) {
            toast.error(error instanceof Error ? error.message : String(error));
        } finally {
            stateControls.showWaitingCheckbox.updateState(false);
        }
    };

    return (
        <section className="voice-library" aria-labelledby="voice-library-heading">
            <div className="studio-section-heading">
                <div>
                    <h2 id="voice-library-heading">Voice library</h2>
                    <p>{models.length} {models.length === 1 ? "model" : "models"} installed</p>
                </div>
                <button type="button" className="studio-button" onClick={() => stateControls.showModelSlotManagerCheckbox.updateState(true)}>
                    <FontAwesomeIcon icon={faSliders} /> Manage models
                </button>
            </div>
            {models.length ? (
                <>
                    <div className="voice-library-sort" role="group" aria-label="Sort models">
                        <button type="button" className="studio-button" aria-pressed={sortType === "slot"} onClick={() => setSortType("slot")}>
                            <FontAwesomeIcon icon={faArrowDown19} /> Slot
                        </button>
                        <button type="button" className="studio-button" aria-pressed={sortType === "name"} onClick={() => setSortType("name")}>
                            <FontAwesomeIcon icon={faArrowDownAZ} /> Name
                        </button>
                    </div>
                    <div className="voice-library-grid">
                        {models.map((model) => {
                            const isSelected = model.slotIndex === settings.modelSlotIndex;
                            const image = model.iconFile ? `${settings.voiceChangerParams.model_dir}/${model.slotIndex}/${model.iconFile.split(/[\/\\]/).pop()}` : null;
                            return (
                                <button key={model.slotIndex} type="button" className="voice-card" aria-pressed={isSelected} onClick={() => selectModel(model.slotIndex)}>
                                    <span className="voice-card-art">
                                        {image ? <img src={image} alt="" loading="lazy" /> : <FontAwesomeIcon icon={faWaveSquare} />}
                                        {isSelected && <span className="voice-card-check"><FontAwesomeIcon icon={faCheck} /></span>}
                                    </span>
                                    <span className="voice-card-caption">
                                        <strong title={model.name}>{model.name || `Slot ${model.slotIndex}`}</strong>
                                        <small>{model.voiceChangerType}</small>
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                </>
            ) : (
                <div className="voice-library-empty">
                    <FontAwesomeIcon icon={faWaveSquare} />
                    <p>Upload a voice model or download a sample in Manage models.</p>
                </div>
            )}
        </section>
    );
};
