import React, { useEffect, useMemo, useState } from "react";
import { useAppState } from "../../001_provider/001_AppStateProvider";
import { ModelFileKind, ModelUploadSetting, VoiceChangerType, fileSelector } from "@dannadori/voice-changer-client-js";
import { useMessageBuilder } from "../../hooks/useMessageBuilder";
import { ModelSlotManagerDialogScreen } from "./904_ModelSlotManagerDialog";
import { checkExtention, trimfileName } from "../../utils/utils";

export type FileUploaderScreenProps = {
    screen: ModelSlotManagerDialogScreen;
    targetIndex: number;
    close: () => void;
    backToSlotManager: () => void;
};

// Define available embedders
const RVC_EMBEDDERS = {
    hubert_base: "Hubert (Default)",
    spin_base: "SPIN",
} as const;

type RvcEmbedderType = keyof typeof RVC_EMBEDDERS;

export const FileUploaderScreen = (props: FileUploaderScreenProps) => {
    const { serverSetting } = useAppState();
    const [voiceChangerType, setVoiceChangerType] = useState<VoiceChangerType>("RVC");
    const [selectedEmbedder, setSelectedEmbedder] = useState<RvcEmbedderType>("hubert_base"); // New state for selected embedder
    const [uploadSetting, setUploadSetting] = useState<ModelUploadSetting>();
    const messageBuilderState = useMessageBuilder();

    useMemo(() => {
        messageBuilderState.setMessage(__filename, "header_message", { ja: "ファイルをアップロードしてください. 対象：", en: "Upload Files for " });
        messageBuilderState.setMessage(__filename, "back", { ja: "戻る", en: "back" });
        messageBuilderState.setMessage(__filename, "select", { ja: "ファイル選択", en: "select file" });
        messageBuilderState.setMessage(__filename, "upload", { ja: "アップロード", en: "upload" });
        messageBuilderState.setMessage(__filename, "uploading", { ja: "アップロード中", en: "uploading" });
        messageBuilderState.setMessage(__filename, "rvc-embedder-select-label", { ja: "Embedderタイプ:", en: "Embedder Type:" });
        messageBuilderState.setMessage(__filename, "alert-model-ext", {
            ja: "ファイルの拡張子は次のモノである必要があります。",
            en: "extension of file should be the following.",
        });
        messageBuilderState.setMessage(__filename, "alert-model-file", {
            ja: "ファイルが選択されていません",
            en: "file is not selected.",
        });
    }, []);

    useEffect(() => {
        const newParams: { embedder?: RvcEmbedderType } = {};
        if (voiceChangerType === "RVC") {
            newParams.embedder = selectedEmbedder;
        }
        setUploadSetting(prevSetting => {
            const currentFiles = prevSetting?.files || [];
            const currentInternalParams = prevSetting?.params || {};

            return {
                ...(prevSetting || { voiceChangerType: voiceChangerType, slot: props.targetIndex, isSampleMode: false, sampleId: null }),
                voiceChangerType: voiceChangerType,
                slot: props.targetIndex,
                isSampleMode: false,
                sampleId: null,
                files: currentFiles,
                params: {
                    ...currentInternalParams,
                    ...newParams
                },
            };
        });
    }, [props.targetIndex, voiceChangerType, selectedEmbedder]);

    const resetUploadSettingState = () => {
        const newResetParams: { embedder?: RvcEmbedderType } = {};
        if (voiceChangerType === "RVC") {
            newResetParams.embedder = selectedEmbedder;
        }
        setUploadSetting({
            voiceChangerType: voiceChangerType,
            slot: props.targetIndex,
            isSampleMode: false,
            sampleId: null,
            files: [],
            params: newResetParams,
        });
    };

    const screen = useMemo(() => {
        if (props.screen != "FileUploader") {
            return <></>;
        }

        const vcTypeOptions = Object.values(VoiceChangerType).map((x) => {
            return (
                <option key={x} value={x}>
                    {x}
                </option>
            );
        });

        const rvcEmbedderOptions = Object.entries(RVC_EMBEDDERS).map(([value, label]) => {
            return (
                <option key={value} value={value}>
                    {label}
                </option>
            );
        });

        const checkModelSetting = (setting: ModelUploadSetting) => {
            if (setting.voiceChangerType == "RVC") {
                const enough = !!setting.files.find((x) => {
                    return x.kind == "rvcModel";
                });
                return enough;
            }
            return false;
        };

        const generateFileRow = (setting: ModelUploadSetting, title: string, kind: ModelFileKind, ext: string[], dir: string = "") => {
            const selectedFile = setting.files.find((x) => {
                return x.kind == kind;
            });
            const selectedFilename = selectedFile?.file.name || "";
            return (
                <div key={`${title}`} className="file-uploader-file-select-row">
                    <div className="file-uploader-file-select-row-label">{title}:</div>
                    <div className="file-uploader-file-select-row-value">{trimfileName(selectedFilename, 30)}</div>
                    <div
                        className="file-uploader-file-select-row-button"
                        onClick={async () => {
                            const file = await fileSelector("");
                            if (checkExtention(file.name, ext) == false) {
                                const alertMessage = `${messageBuilderState.getMessage(__filename, "alert-model-ext")} ${ext}`;
                                alert(alertMessage);
                                return;
                            }
                            if (selectedFile) {
                                selectedFile.file = file;
                            } else {
                                setting.files.push({ kind: kind, file: file, dir: dir });
                            }
                            setUploadSetting({ ...setting });
                        }}
                    >
                        {messageBuilderState.getMessage(__filename, "select")}
                    </div>
                </div>
            );
        };

        const generateFileRowsByVCType = (vcType: VoiceChangerType) => {
            const rows: JSX.Element[] = [];
            if (vcType == "RVC") {
                rows.push(generateFileRow(uploadSetting!, "Model", "rvcModel", ["pth", "onnx", 'safetensors']));
                rows.push(generateFileRow(uploadSetting!, "Index", "rvcIndex", ["index", "bin"]));
            }
            return rows;
        };
        const fileRows = uploadSetting ? generateFileRowsByVCType(voiceChangerType) : [];

        const buttonLabel = serverSetting.uploadProgress == 0 ? messageBuilderState.getMessage(__filename, "upload") : messageBuilderState.getMessage(__filename, "uploading") + `(${serverSetting.uploadProgress.toFixed(1)}%)`;
        return (
            <div className="dialog-frame">
                <div className="dialog-title">File Uploader</div>
                <div className="dialog-fixed-size-content">
                    <div className="file-uploader-header">
                        {messageBuilderState.getMessage(__filename, "header_message")} Slot[{props.targetIndex}]
                        <span
                            onClick={() => {
                                props.backToSlotManager();
                                resetUploadSettingState();
                            }}
                            className="file-uploader-header-button"
                        >
                            &lt;&lt;{messageBuilderState.getMessage(__filename, "back")}
                        </span>
                    </div>
                    <div className="file-uploader-voice-changer-select">
                        VoiceChangerType:
                        <select
                            value={voiceChangerType}
                            onChange={(e) => {
                                const newVcType = e.target.value as VoiceChangerType;
                                setVoiceChangerType(newVcType);
                                if (newVcType !== "RVC") {
                                    setSelectedEmbedder("hubert_base");
                                }
                            }}
                        >
                            {vcTypeOptions}
                        </select>
                    </div>

                    {voiceChangerType === "RVC" && (
                        <div className="file-uploader-voice-changer-select">
                            {messageBuilderState.getMessage(__filename, "rvc-embedder-select-label")}
                            <select
                                value={selectedEmbedder}
                                onChange={(e) => {
                                    setSelectedEmbedder(e.target.value as RvcEmbedderType);
                                }}
                            >
                                {rvcEmbedderOptions}
                            </select>
                        </div>
                    )}

                    <div className="file-uploader-file-select-container">{fileRows}</div>
                    <div className="file-uploader-file-select-upload-button-container">
                        <div
                            className="file-uploader-file-select-upload-button"
                            onClick={() => {
                                if (!uploadSetting) {
                                    return;
                                }
                                if (serverSetting.uploadProgress != 0) {
                                    return;
                                }
                                if (checkModelSetting(uploadSetting)) {
                                    const finalUploadSetting = {
                                        ...uploadSetting,
                                        embedder: voiceChangerType === "RVC" ? selectedEmbedder : undefined,
                                    };
                                    console.log(finalUploadSetting);
                                    serverSetting.uploadModel(finalUploadSetting).then(() => {
                                        props.backToSlotManager();
                                        resetUploadSettingState();
                                    });
                                } else {
                                    const errorMessage = messageBuilderState.getMessage(__filename, "alert-model-file");
                                    alert(errorMessage);
                                }
                            }}
                        >
                            {buttonLabel}
                        </div>
                    </div>
                </div>
            </div>
        );
    }, [props.screen, props.targetIndex, voiceChangerType, selectedEmbedder, uploadSetting, serverSetting.uploadModel, serverSetting.uploadProgress, messageBuilderState]);

    return screen;
};
