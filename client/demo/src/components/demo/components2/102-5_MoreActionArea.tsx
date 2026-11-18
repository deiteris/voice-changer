import React, { useMemo } from "react";
import { useGuiState } from "../001_GuiStateProvider";

export type MoreActionAreaProps = {};

export const MoreActionArea = (_props: MoreActionAreaProps) => {
    const { stateControls } = useGuiState();

    const serverIORecorderRow = useMemo(() => {
        const onOpenMergeLabClicked = () => {
            stateControls.showMergeLabCheckbox.updateState(true);
        };
        const onOpenAdvancedSettingClicked = () => {
            stateControls.showAdvancedSettingCheckbox.updateState(true);
        };
        const onOpenGetServerInformationClicked = () => {
            stateControls.showGetServerInformationCheckbox.updateState(true);
        };
        const onOpenGetClientInformationClicked = () => {
            stateControls.showGetClientInformationCheckbox.updateState(true);
        };
        return (
            <>
                <div className="config-sub-area-control">
                    <div className="config-sub-area-control-field config-sub-area-control-field-long">
                        <div className="config-sub-area-buttons">
                            <button type="button" onClick={onOpenMergeLabClicked} className="studio-button">
                                Merge Lab
                            </button>
                            <button type="button" onClick={onOpenAdvancedSettingClicked} className="studio-button">
                                Advanced settings
                            </button>
                            <button type="button" onClick={onOpenGetServerInformationClicked} className="studio-button">
                                Server Info
                            </button>
                            <button type="button" onClick={onOpenGetClientInformationClicked} className="studio-button">
                                Client Info
                            </button>
                        </div>
                    </div>
                </div>
            </>
        );
    }, [stateControls]);

    return <div className="config-sub-area">{serverIORecorderRow}</div>;
};
