import React, { useMemo } from "react"
import { useAppRoot } from "../../001_provider/001_AppRootProvider"
import { generateComponent } from "./002_ComponentGenerator"

export const ModelSlotControl = () => {
    const { appGuiSettingState } = useAppRoot()
    const componentSettings = appGuiSettingState.appGuiSetting.front.modelSlotControl

    const deviceSetting = useMemo(() => {
        if (!componentSettings || componentSettings.length == 0) {
            return <></>
        }
        const components = componentSettings.map((x, index) => {
            const c = generateComponent(x.name, x.options)
            return <div key={`${x.name}_${index}`} className={`studio-section studio-section-${x.name}`}>{c}</div>
        })
        return (
            <>
                <div className="partition">
                    <main className="partition-content studio-workspace">
                        {components}
                    </main>
                </div>
            </>
        )
    }, [])

    return deviceSetting
}
