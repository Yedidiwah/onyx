import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring } from "remotion";
import React from "react";

export const HelloWorld: React.FC<{
    titleToReplace: string;
    subTitleToReplace: string;
}> = ({ titleToReplace = "AUS ➡️ IWS", subTitleToReplace = "Price: $1,540 | Seats: 7" }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    // אנימציות
    const titleOpacity = spring({ frame: frame - 15, fps, config: { damping: 100 } });
    const titleY = spring({ frame: frame - 15, fps, from: 50, to: 0 });
    
    const subOpacity = spring({ frame: frame - 45, fps, config: { damping: 100 } });
    const subScale = spring({ frame: frame - 45, fps, from: 0.8, to: 1 });

    return (
        // רקע יוקרתי כהה שמיוצר בקוד ולא דורש שום וידאו חיצוני
        <AbsoluteFill className="bg-gradient-to-br from-slate-900 via-black to-slate-800 text-white font-sans">
            
            <AbsoluteFill className="flex flex-col items-center justify-center p-10">
                
                <div 
                    style={{ opacity: titleOpacity, transform: `translateY(${titleY}px)` }} 
                    className="flex flex-col items-center mb-16"
                >
                    <div className="text-3xl font-semibold mb-6 text-gray-300 tracking-[0.3em] uppercase bg-white/5 px-6 py-2 rounded-full border border-white/10 shadow-lg">
                        ✈️ VIP Empty Leg
                    </div>
                    <h2 className="text-9xl font-black text-white drop-shadow-[0_10px_20px_rgba(0,0,0,0.8)]">
                        {titleToReplace}
                    </h2>
                </div>

                <div 
                    style={{ opacity: subOpacity, transform: `scale(${subScale})` }}
                    className="bg-white/5 backdrop-blur-md border border-white/10 px-12 py-6 rounded-3xl shadow-2xl"
                >
                    <p className="text-6xl font-medium text-emerald-400 drop-shadow-md">
                        {subTitleToReplace}
                    </p>
                </div>

                <div 
                    style={{ opacity: spring({ frame: frame - 90, fps }) }}
                    className="absolute bottom-24 text-4xl font-light tracking-widest text-white/60 uppercase"
                >
                    Link in bio to book
                </div>
            </AbsoluteFill>
        </AbsoluteFill>
    );
};
