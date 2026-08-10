import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, OffthreadVideo, staticFile } from "remotion";
import React from "react";

export const HelloWorld: React.FC<{
    titleToReplace: string;
    subTitleToReplace: string;
}> = ({ titleToReplace = "AUS ➡️ IWS", subTitleToReplace = "Price: $1,540 | Seats: 7" }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const titleOpacity = spring({ frame: frame - 15, fps, config: { damping: 100 } });
    const titleY = spring({ frame: frame - 15, fps, from: 50, to: 0 });
    
    const subOpacity = spring({ frame: frame - 45, fps, config: { damping: 100 } });
    const subScale = spring({ frame: frame - 45, fps, from: 0.8, to: 1 });

    return (
        <AbsoluteFill className="bg-black text-white font-sans">
            
            <OffthreadVideo
                src={staticFile("bg.mp4")} 
                style={{
                    position: "absolute",
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                }}
                muted
                loop
            />
            
            <AbsoluteFill className="bg-black/50" />

            <AbsoluteFill className="flex flex-col items-center justify-center p-10">
                <div 
                    style={{ opacity: titleOpacity, transform: `translateY(${titleY}px)` }} 
                    className="flex flex-col items-center mb-16"
                >
                    {/* הוגדל מ-3xl ל-5xl */}
                    <div className="text-5xl font-semibold mb-6 text-gray-300 tracking-[0.3em] uppercase bg-white/10 px-8 py-3 rounded-full border border-white/20 shadow-lg backdrop-blur-sm">
                        ✈️ VIP Empty Leg
                    </div>
                    {/* הוגדל לממדי ענק: text-[12rem] (בערך 190 פיקסלים) */}
                    <h2 className="text-[12rem] font-black text-white drop-shadow-[0_15px_25px_rgba(0,0,0,0.9)] leading-none mb-4">
                        {titleToReplace}
                    </h2>
                </div>

                <div 
                    style={{ opacity: subOpacity, transform: `scale(${subScale})` }}
                    className="bg-black/50 backdrop-blur-md border border-white/20 px-16 py-8 rounded-[3rem] shadow-2xl mt-4"
                >
                    {/* הוגדל מ-6xl ל-8xl */}
                    <p className="text-8xl font-medium text-emerald-400 drop-shadow-md">
                        {subTitleToReplace}
                    </p>
                </div>

                <div 
                    style={{ opacity: spring({ frame: frame - 90, fps }) }}
                    className="absolute bottom-24 text-5xl font-light tracking-widest text-white/90 uppercase drop-shadow-md"
                >
                    Link in bio to book
                </div>
            </AbsoluteFill>
        </AbsoluteFill>
    );
};
