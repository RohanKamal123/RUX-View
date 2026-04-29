import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function POST(request: Request) {
    try {
        const body = await request.json()
        const { fitnessLevel, injuries } = body

        // Basic filtering logic
        // In a real app, this would be more complex
        let whereClause: any = {}

        if (fitnessLevel === 'Beginner') {
            whereClause.difficulty = 'Beginner'
        } else if (fitnessLevel === 'Intermediate') {
            whereClause.difficulty = { in: ['Beginner', 'Intermediate'] }
        }
        // Advanced sees all

        // Filter out exercises with contraindications matching injuries
        // This is a simple string check, ideally we'd have a many-to-many relation for injuries
        // But for this minimal MVP, we'll fetch all and filter in JS if needed, or use simple exclusion if possible.
        // Since SQLite doesn't support array contains easily for string fields, we'll fetch and filter.

        // Actually, let's just fetch based on difficulty first
        const exercises = await prisma.exercise.findMany({
            where: whereClause,
        })

        // Filter by injuries in memory
        const filteredExercises = exercises.filter((exercise) => {
            if (!injuries || injuries.length === 0) return true
            if (!exercise.contraindications) return true

            // Check if any injury matches the contraindications
            // injuries is expected to be an array of strings like ['knees', 'back']
            // contraindications is a string like "Knee pain"

            const contraindicationsLower = exercise.contraindications.toLowerCase()
            for (const injury of injuries) {
                if (contraindicationsLower.includes(injury.toLowerCase())) {
                    return false
                }
            }
            return true
        })

        return NextResponse.json(filteredExercises)
    } catch (error) {
        console.error('Error fetching exercises:', error)
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 })
    }
}
