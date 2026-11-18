import React, { useMemo } from "react";
import { useGuiState } from "./001_GuiStateProvider";
import { useAppState } from "../../001_provider/001_AppStateProvider";
import { RVCModelSlot, fileSelector } from "@dannadori/voice-changer-client-js";
import { useMessageBuilder } from "../../hooks/useMessageBuilder";
import { ModelSlotManagerDialogScreen } from "./904_ModelSlotManagerDialog";
import { checkExtention, trimfileName } from "../../utils/utils";
import { faWaveSquare } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

export type MainScreenProps = {
    screen: ModelSlotManagerDialogScreen;
    close: () => void;
    openSampleDownloader: (slotIndex: number) => void;
    openFileUploader: (slotIndex: number) => void;
    openEditor: (slotIndex: number) => void;
};

export const MainScreen = (props: MainScreenProps) => {
    const { serverSetting } = useAppState();
    const guiState = useGuiState();
    const messageBuilderState = useMessageBuilder();
    useMemo(() => {
        messageBuilderState.setMessage(__filename, "change_icon", { ja: "アイコン変更", en: "change icon" });
        messageBuilderState.setMessage(__filename, "rename", { ja: "リネーム", en: "rename" });
        messageBuilderState.setMessage(__filename, "download", { ja: "ダウンロード", en: "download" });
        messageBuilderState.setMessage(__filename, "terms_of_use", { ja: "利用規約", en: "terms of use" });
        messageBuilderState.setMessage(__filename, "sample", { ja: "サンプル", en: "DL sample" });
        messageBuilderState.setMessage(__filename, "upload", { ja: "アップロード", en: "upload" });
        messageBuilderState.setMessage(__filename, "edit", { ja: "編集", en: "edit" });
        messageBuilderState.setMessage(__filename, "close", { ja: "閉じる", en: "close" });
        messageBuilderState.setMessage(__filename, "empty_slot", { ja: "空きスロット", en: "Empty slot" });
    }, []);

    const screen = useMemo(() => {
        if (props.screen != "Main") {
            return <></>;
        }
        if (!serverSetting.serverSetting.modelSlots) {
            return <></>;
        }

        const iconAction = async (index: number) => {
            if (!serverSetting.serverSetting.modelSlots[index].name || serverSetting.serverSetting.modelSlots[index].name.length == 0) {
                return;
            }

            const file = await fileSelector("");
            if (checkExtention(file.name, ["png", "jpg", "jpeg", "gif"]) == false) {
                alert(`サムネイルの拡張子は".png", ".jpg", ".jpeg", ".gif"である必要があります。`);
                return;
            }
            try {
                await serverSetting.uploadAssets(index, "iconFile", file);
            } catch (error) {
                alert(error instanceof Error ? error.message : String(error));
            }
        };

        const nameValueAction = async (index: number) => {
            if (!serverSetting.serverSetting.modelSlots[index].name || serverSetting.serverSetting.modelSlots[index].name.length == 0) {
                return;
            }
            // Open Text Input Dialog
            const p = new Promise<string>((resolve) => {
                guiState.setTextInputResolve({ resolve: resolve });
            });
            guiState.stateControls.showTextInputCheckbox.updateState(true);
            const text = await p;

            // Send to Server
            if (text.length > 0) {
                console.log("input text:", text);
                await serverSetting.updateModelInfo(index, "name", text);
            }
        };

        const fileValueAction = (url: string) => {
            if (url.length == 0) {
                return;
            }
            const link = document.createElement("a");
            link.href = "./" + url;
            link.download = url.replace(/^.*[\\\/]/, "");
            link.click();
            link.remove();
        };

        const closeButtonRow = (
            <div className="body-row split-3-4-3 left-padding-1">
                <div className="body-item-text"></div>
                <div className="body-button-container body-button-container-space-around">
                    <button type="button"
                        className="body-button"
                        onClick={() => {
                            props.close();
                        }}
                    >
                        {messageBuilderState.getMessage(__filename, "close")}
                    </button>
                </div>
                <div className="body-item-text"></div>
            </div>
        );

        const slotRow = serverSetting.serverSetting.modelSlots.map((x, index) => {
            // モデルのアイコン
            const generateIconArea = (slotIndex: number, iconUrl: string | null, canChangeIcon: boolean) => {
                const artwork = iconUrl ? (
                    <img src={`${serverSetting.serverSetting.voiceChangerParams.model_dir}/${slotIndex}/${iconUrl.split(/[\/\\]/).pop()}`} className="model-slot-icon" alt="" />
                ) : (
                    <span className="model-slot-icon studio-slot-placeholder" aria-hidden="true"><FontAwesomeIcon icon={faWaveSquare} /></span>
                );
                if (!canChangeIcon) return artwork;

                return (
                    <button
                        type="button"
                        className="studio-slot-icon-button"
                        title={messageBuilderState.getMessage(__filename, "change_icon")}
                        aria-label={`${messageBuilderState.getMessage(__filename, "change_icon")} (${slotIndex})`}
                        onClick={() => iconAction(slotIndex)}
                    >
                        {artwork}
                    </button>
                );
            };

            // モデルの名前
            const generateNameRow = (slotIndex: number, name: string, termsOfUseUrl: string) => {
                const nameValueClass = name.length > 0 ? "model-slot-detail-row-value-pointable tooltip" : "model-slot-detail-row-value";
                const displayName = name || messageBuilderState.getMessage(__filename, "empty_slot");
                const termOfUseUrlLink =
                    termsOfUseUrl.length > 0 ? (
                        <a href={termsOfUseUrl} target="_blank" rel="noopener noreferrer" className="body-item-text-small">
                            [{messageBuilderState.getMessage(__filename, "terms_of_use")}]
                        </a>
                    ) : (
                        <></>
                    );

                return (
                    <div className="model-slot-detail-row">
                        <div className="model-slot-detail-row-label">[{slotIndex}]</div>
                        <div
                            className={nameValueClass}
                            onClick={() => {
                                nameValueAction(slotIndex);
                            }}
                        >
                            {displayName}
                            <div className="tooltip-text tooltip-text-thin">{messageBuilderState.getMessage(__filename, "rename")}</div>
                        </div>
                        <div className="">{termOfUseUrlLink}</div>
                    </div>
                );
            };

            // モデルを構成するファイル
            const generateFileRow = (title: string, filePath: string) => {
                const fileValueClass = filePath.length > 0 ? "model-slot-detail-row-value-download  tooltip" : "model-slot-detail-row-value";
                return (
                    <div key={`${title}`} className="model-slot-detail-row">
                        <div className="model-slot-detail-row-label">{title}:</div>
                        <div
                            className={fileValueClass}
                            onClick={() => {
                                fileValueAction(filePath);
                            }}
                        >
                            {trimfileName(filePath, 20)}
                            <div className="tooltip-text tooltip-text-thin">{messageBuilderState.getMessage(__filename, "download")}</div>
                        </div>
                    </div>
                );
            };

            // その他情報欄
            const generateInfoRow = (info: string) => {
                return (
                    <div className="model-slot-detail-row">
                        <div className="model-slot-detail-row-label">info: </div>
                        <div className="model-slot-detail-row-value">{info}</div>
                        <div className=""></div>
                    </div>
                );
            };

            let iconArea = <></>;
            let nameRow = <></>;
            const fileRows = [];
            let infoRow = <></>;
            if (x.voiceChangerType == "RVC") {
                const slotInfo = x as RVCModelSlot;
                iconArea = generateIconArea(index, slotInfo.iconFile, true);
                nameRow = generateNameRow(index, slotInfo.name, slotInfo.termsOfUseUrl);
                fileRows.push(generateFileRow("model", slotInfo.modelFile));
                fileRows.push(generateFileRow("index", slotInfo.indexFile));
                infoRow = generateInfoRow(`${slotInfo.f0 ? "f0" : "nof0"}, ${slotInfo.samplingRate}, ${slotInfo.embChannels}, ${slotInfo.modelType}, ${slotInfo.defaultTune}, ${slotInfo.defaultFormantShift}, ${slotInfo.defaultIndexRatio}, ${slotInfo.defaultProtect}`);
            } else {
                iconArea = generateIconArea(index, null, false);
                nameRow = generateNameRow(index, "", "");
            }
            return (
                <div key={index} className="model-slot">
                    {iconArea}
                    <div className="model-slot-detail">
                        {nameRow}
                        {fileRows}
                        {infoRow}
                    </div>
                    <div className="model-slot-buttons">
                        <button type="button"
                            className="model-slot-button"
                            onClick={() => {
                                props.openFileUploader(index);
                            }}
                        >
                            {messageBuilderState.getMessage(__filename, "upload")}
                        </button>
                        <button type="button"
                            className="model-slot-button"
                            onClick={() => {
                                props.openSampleDownloader(index);
                            }}
                        >
                            {messageBuilderState.getMessage(__filename, "sample")}
                        </button>
                        <button type="button"
                            className="model-slot-button"
                            onClick={() => {
                                props.openEditor(index);
                            }}
                        >
                            {messageBuilderState.getMessage(__filename, "edit")}
                        </button>
                    </div>
                </div>
            );
        });

        return (
            <div className="dialog-frame">
                <h2 className="dialog-title">Manage models</h2>
                <div className="dialog-fixed-size-content">
                    <div className="model-slot-container">{slotRow}</div>
                    {closeButtonRow}
                </div>
            </div>
        );
    }, [props.screen, serverSetting.serverSetting]);

    return screen;
};
