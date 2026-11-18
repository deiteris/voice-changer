import React from "react";
import { faGithub } from "@fortawesome/free-brands-svg-icons";
import { faRotateLeft, faWaveSquare } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useIndexedDB } from "@dannadori/voice-changer-client-js";
import { INDEXEDDB_KEY_AUDIO_OUTPUT, isDesktopApp } from "../../../const";
import { useAppRoot } from "../../../001_provider/001_AppRootProvider";
import { useAppState } from "../../../001_provider/001_AppStateProvider";

export type HeaderAreaProps = {
    mainTitle: string;
    subTitle: string;
};

const repositoryUrl = "https://github.com/deiteris/voice-changer";

export const HeaderArea = ({ mainTitle, subTitle }: HeaderAreaProps) => {
    const { appGuiSettingState } = useAppRoot();
    const { clearSetting } = useAppState();
    const { removeItem, removeDB } = useIndexedDB({ clientType: null });
    const { version, edition } = appGuiSettingState;

    const onClearSettingClicked = async () => {
        await clearSetting();
        await removeItem(INDEXEDDB_KEY_AUDIO_OUTPUT);
        await removeDB();
        location.reload();
    };

    return (
        <>
            <header className="studio-header">
                <div className="studio-brand">
                    <span className="studio-brand-mark"><FontAwesomeIcon icon={faWaveSquare} /></span>
                    <span>Voice Changer</span>
                </div>
                <div className="studio-header-actions">
                    <span className="studio-version">{[version, edition].filter(Boolean).join(" · ")}</span>
                    {isDesktopApp() ? (
                        <button type="button" className="studio-button studio-icon-button" aria-label="GitHub" onClick={() => {
                            // @ts-ignore
                            window.electronAPI.openBrowser(repositoryUrl);
                        }}>
                            <FontAwesomeIcon icon={faGithub} />
                        </button>
                    ) : (
                        <a className="studio-button studio-icon-button" aria-label="GitHub" href={repositoryUrl} target="_blank" rel="noopener noreferrer">
                            <FontAwesomeIcon icon={faGithub} />
                        </a>
                    )}
                    <button type="button" className="studio-button studio-reset-button" aria-label="Reset settings" onClick={onClearSettingClicked}>
                        <FontAwesomeIcon icon={faRotateLeft} /> <span>Reset settings</span>
                    </button>
                </div>
            </header>
            <div className="studio-intro">
                <h1>{mainTitle}</h1>
                <p>{subTitle || "Choose a voice model, tune your sound, and convert live audio."}</p>
            </div>
        </>
    );
};
