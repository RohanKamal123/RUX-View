import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  const exercises = [
    {
      name: 'Push-ups',
      description: 'A classic upper body exercise.',
      difficulty: 'Beginner',
      category: 'Strength',
      contraindications: 'Wrist pain',
    },
    {
      name: 'Squats',
      description: 'Fundamental lower body exercise.',
      difficulty: 'Beginner',
      category: 'Strength',
      contraindications: 'Knee pain',
    },
    {
      name: 'Running',
      description: 'Cardiovascular exercise.',
      difficulty: 'Intermediate',
      category: 'Cardio',
      contraindications: 'Joint pain',
    },
    {
      name: 'Yoga Stretch',
      description: 'Basic stretching routine.',
      difficulty: 'Beginner',
      category: 'Flexibility',
      contraindications: null,
    },
     {
      name: 'Burpees',
      description: 'Full body cardio and strength.',
      difficulty: 'Advanced',
      category: 'Cardio',
      contraindications: 'Heart conditions, Joint pain',
    },
  ]

  for (const exercise of exercises) {
    await prisma.exercise.create({
      data: exercise,
    })
  }
}

main()
  .then(async () => {
    await prisma.$disconnect()
  })
  .catch(async (e) => {
    console.error(e)
    await prisma.$disconnect()
    process.exit(1)
  })
