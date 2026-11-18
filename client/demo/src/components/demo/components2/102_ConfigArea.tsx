import React, { useMemo } from "react"
import { QualityArea } from "./102-1_QualityArea"
import { ConvertArea } from "./102-2_ConvertArea"
import { DeviceArea } from "./102-3_DeviceArea"
import { RecorderArea } from "./102-4_RecorderArea"
import { MoreActionArea } from "./102-5_MoreActionArea"

export type ConfigAreaProps = {
    detectors: string[]
    inputChunkNums: number[]
}


export const ConfigArea = (props: ConfigAreaProps) => {
    const configArea = useMemo(() => {
        return (
            <section className="studio-settings" aria-labelledby="studio-settings-heading">
                <h2 id="studio-settings-heading">Audio settings</h2>
                <div className="studio-settings-grid">
                    <section className="config-area">
                        <h3>Devices &amp; recording</h3>
                        <DeviceArea />
                        <RecorderArea />
                    </section>
                    <section className="config-area">
                        <h3>Conversion quality</h3>
                        <QualityArea detectors={props.detectors} />
                        <ConvertArea inputChunkNums={props.inputChunkNums} />
                        <MoreActionArea />
                    </section>
                </div>
            </section>

        )
    }, [])

    return configArea
}
