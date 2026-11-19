import React, { useState } from "react";
import { faGithub } from "@fortawesome/free-brands-svg-icons";
import { faPowerOff, faRotateLeft, faWaveSquare } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useIndexedDB } from "@dannadori/voice-changer-client-js";
import { toast } from "react-toastify";
import { INDEXEDDB_KEY_AUDIO_OUTPUT, isDesktopApp } from "../../../const";
import { useAppRoot } from "../../../001_provider/001_AppRootProvider";
import { useAppState } from "../../../001_provider/001_AppStateProvider";

export type HeaderAreaProps = {
    mainTitle: string;
    subTitle: string;
};

declare global {
    interface Window {
        voiceChangerDesktop?: { quit: () => Promise<void> };
    }
}

const repositoryUrl = "https://github.com/deiteris/voice-changer";

export const HeaderArea = ({ mainTitle, subTitle }: HeaderAreaProps) => {
    const { appGuiSettingState } = useAppRoot();
    const { clearSetting } = useAppState();
    const { removeItem, removeDB } = useIndexedDB({ clientType: null });
    const { version, edition } = appGuiSettingState;
    const [quitting, setQuitting] = useState(false);
    const desktop = window.voiceChangerDesktop;

    const onClearSettingClicked = async () => {
        await clearSetting();
        await removeItem(INDEXEDDB_KEY_AUDIO_OUTPUT);
        await removeDB();
        location.reload();
    };

    const onQuitClicked = async () => {
        if (!desktop) return;
        setQuitting(true);
        try {
            await desktop.quit();
        } catch {
            setQuitting(false);
            toast.error("Couldn't quit Voice Changer. Try again.");
        }
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
                    {desktop && (
                        <button type="button" className="studio-button" disabled={quitting} onClick={onQuitClicked}>
                            <FontAwesomeIcon icon={faPowerOff} /> {quitting ? "Quitting…" : "Quit"}
                        </button>
                    )}
                </div>
            </header>
            <div className="studio-intro">
                <h1>{mainTitle}</h1>
                <p>{subTitle || "Choose a voice model, tune your sound, and convert live audio."}</p>
            </div>
        </>
    );
};
