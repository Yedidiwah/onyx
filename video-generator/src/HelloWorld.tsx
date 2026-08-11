import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, Video, staticFile, Series, Img, interpolate } from "remotion";
import React from "react";

export const HelloWorld: React.FC<{
    titleToReplace: string;
    subTitleToReplace: string;
    video1?: string;
    video2?: string;
    video3?: string;
}> = ({ 
    titleToReplace = "AUS ➡️ IWS", 
    subTitleToReplace = "Price: $1,540 | Seats: 7",
    video1 = "part1_1.mp4",
    video2 = "part2_1.mp4",
    video3 = "part3_1.mp4"
}) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    // אנימציית כניסה לטקסט
    const titleOpacityIn = spring({ frame: frame - 15, fps, config: { damping: 100 } });
    const titleY = spring({ frame: frame - 15, fps, from: 50, to: 0 });
    const subOpacityIn = spring({ frame: frame - 45, fps, config: { damping: 100 } });
    const subScale = spring({ frame: frame - 45, fps, from: 0.8, to: 1 });
    const linkOpacityIn = spring({ frame: frame - 90, fps });

    // אנימציית יציאה (Fade out) לטקסט החל מפריים 435 לקראת הלוגו
    const textOpacityOut = interpolate(frame, [435, 450], [1, 0], { extrapolateRight: "clamp" });
    
    // חישוב שקיפות סופית לטקסט 
    const finalTitleOpacity = titleOpacityIn * textOpacityOut;
    const finalSubOpacity = subOpacityIn * textOpacityOut;
    const finalLinkOpacity = linkOpacityIn * textOpacityOut;

    // אנימציית כניסה אלגנטית ללוגו בחלק הרביעי
    const logoOpacity = spring({ frame: frame - 450, fps, config: { damping: 100 } });
    const logoScale = spring({ frame: frame - 450, fps, from: 0.9, to: 1, config: { damping: 100 } });

    return (
        <AbsoluteFill className="bg-black text-white font-sans">
            
            <AbsoluteFill>
                <Series>
                    {/* חלק 1 - 5 שניות */}
                    <Series.Sequence durationInFrames={150}>
                        <Video src={staticFile(video1)} style={{ width: "100%", height: "100%", objectFit: "cover" }} muted />
                    </Series.Sequence>
                    
                    {/* חלק 2 - 5 שניות */}
                    <Series.Sequence durationInFrames={150}>
                        <Video src={staticFile(video2)} style={{ width: "100%", height: "100%", objectFit: "cover" }} muted />
                    </Series.Sequence>
                    
                    {/* חלק 3 - 5 שניות */}
                    <Series.Sequence durationInFrames={150}>
                        <Video src={staticFile(video3)} style={{ width: "100%", height: "100%", objectFit: "cover" }} muted />
                    </Series.Sequence>

                    {/* חלק 4 - אאוטרו יוקרתי (3 שניות) */}
                    <Series.Sequence durationInFrames={90}>
                        <AbsoluteFill className="bg-[#050505] flex items-center justify-center">
                            <div 
                                style={{ opacity: logoOpacity, transform: `scale(${logoScale})`, display: 'flex', flexDirection: 'column', alignItems: 'center' }}
                            >
                                <Img src={staticFile("onyx-logo.png")} style={{ width: "650px", objectFit: "contain" }} />
                                <p className="text-4xl text-gray-400 font-light tracking-[0.3em] mt-8 uppercase drop-shadow-lg">
                                    Fly Exclusively. Book Now.
                                </p>
                            </div>
                        </AbsoluteFill>
                    </Series.Sequence>
                </Series>
            </AbsoluteFill>
            
            {/* רקע הכהה מתחת לטקסט נעלם יחד איתו בפריים 435 */}
            <AbsoluteFill style={{ opacity: textOpacityOut }} className="bg-black/40" />

            {/* שכבת הטקסט המרכזית */}
            <AbsoluteFill className="flex flex-col items-center justify-center p-10 pointer-events-none">
                <div 
                    style={{ opacity: finalTitleOpacity, transform: `translateY(${titleY}px)` }} 
                    className="flex flex-col items-center mb-16"
                >
                    <div className="text-5xl font-semibold mb-6 text-gray-300 tracking-[0.3em] uppercase bg-white/10 px-8 py-3 rounded-full border border-white/20 shadow-lg backdrop-blur-sm">
                        ✈️ VIP Empty Leg
                    </div>
                    <h2 className="text-[12rem] font-black text-white drop-shadow-[0_15px_25px_rgba(0,0,0,0.9)] leading-none mb-4 text-center">
                        {titleToReplace}
                    </h2>
                </div>

                <div 
                    style={{ opacity: finalSubOpacity, transform: `scale(${subScale})` }}
                    className="bg-black/50 backdrop-blur-md border border-white/20 px-16 py-8 rounded-[3rem] shadow-2xl mt-4"
                >
                    <p className="text-8xl font-medium text-emerald-400 drop-shadow-md">
                        {subTitleToReplace}
                    </p>
                </div>

                <div 
                    style={{ opacity: finalLinkOpacity }}
                    className="absolute bottom-24 text-5xl font-light tracking-widest text-white/90 uppercase drop-shadow-md"
                >
                    Link in bio to book
                </div>
            </AbsoluteFill>
        </AbsoluteFill>
    );
};
